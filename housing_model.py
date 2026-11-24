"""Grouped evaluation and estimation of listing prices."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler


AREA_FEATURES = ("Luas_Tanah_m2", "Luas_Bangunan_m2")
ROOM_FEATURES = ("Kamar_Tidur", "Kamar_Mandi")
NUMERIC_FEATURES = (*AREA_FEATURES, *ROOM_FEATURES)
FEATURES = ("Kota", *NUMERIC_FEATURES)
TARGET = "Harga_Rp"
BASELINE = "Median data latih"
CITY_BASELINE = "Median per wilayah"


class CityMedianRegressor:
    def fit(self, features, prices):
        self.city_medians = prices.groupby(features.Kota).median()
        self.global_median = prices.median()
        return self

    def predict(self, features):
        return features.Kota.map(self.city_medians).fillna(self.global_median).to_numpy()


def normalized_keys(series):
    return series.astype("string").str.normalize("NFKC").str.casefold().str.split().str.join(" ")


def prepare_model_data(data):
    """Return eligible rows and mutually exclusive exclusion counts."""
    price = data[TARGET]
    city = normalized_keys(data.Kota)
    location = normalized_keys(data.Lokasi)
    areas = data[list(AREA_FEATURES)]
    rooms = data[list(ROOM_FEATURES)]
    checks = (
        ("Harga penawaran tidak valid", (price.gt(0) & np.isfinite(price))),
        ("Wilayah atau lokasi tidak tersedia", city.fillna("").ne("") & location.fillna("").ne("")),
        ("Luas tanah atau bangunan tidak valid", (areas.gt(0) & np.isfinite(areas)).all(axis=1)),
        ("Jumlah kamar tidak valid", (rooms.gt(0) & np.isfinite(rooms) & rooms.mod(1).eq(0)).all(axis=1)),
    )
    eligible = pd.Series(True, index=data.index)
    excluded = {}
    for reason, valid in checks:
        excluded[reason] = int((eligible & ~valid).sum())
        eligible &= valid
    clean = data.loc[eligible, [*FEATURES, TARGET]].copy()
    clean["location_group"] = city.loc[eligible] + " | " + location.loc[eligible]
    clean["Kota"] = city.loc[eligible].str.title()
    return clean.reset_index(drop=True), excluded


def grouped_splits(rows, n_splits):
    """Keep each normalized location wholly on one side of every split."""
    groups_per_city = rows.groupby("Kota").location_group.nunique()
    if len(groups_per_city) < 2 or len(rows) < n_splits or groups_per_city.min() < n_splits:
        raise ValueError("Belum cukup kelompok lokasi per wilayah untuk melakukan pemisahan data.")
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)
    return list(splitter.split(rows, rows.Kota, groups=rows.location_group))


def holdout_split(rows):
    cities = set(rows.Kota)
    candidates = [
        (train, test) for train, test in grouped_splits(rows, 5)
        if set(rows.iloc[train].Kota) == cities and set(rows.iloc[test].Kota) == cities
    ]
    if not candidates:
        raise ValueError("Tidak ada pembagian lokasi yang mewakili seluruh wilayah di data latih dan uji.")
    return min(candidates, key=lambda pair: abs(len(pair[1]) / len(rows) - .20))


def candidates():
    yield BASELINE, DummyRegressor(strategy="median")
    yield CITY_BASELINE, CityMedianRegressor()
    for name, estimator in (
        ("Ridge", Ridge(alpha=10)),
        ("Gradient boosting", GradientBoostingRegressor(
            n_estimators=140, max_depth=3, learning_rate=.05, random_state=42)),
    ):
        features = ColumnTransformer([
            ("wilayah", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["Kota"]),
            ("angka", make_pipeline(FunctionTransformer(np.log1p), StandardScaler()), list(NUMERIC_FEATURES)),
        ])
        yield name, TransformedTargetRegressor(
            regressor=make_pipeline(features, estimator), func=np.log, inverse_func=np.exp,
        )


@dataclass
class Evaluation:
    selected: str
    estimator: object
    train: pd.DataFrame
    predictions: pd.DataFrame
    scores: pd.DataFrame

    def city_errors(self):
        return self.predictions.groupby("Kota").error.agg(count="size", mae="mean")

    def scenario_bounds(self, city):
        return self.train.loc[self.train.Kota.eq(city), list(NUMERIC_FEATURES)].agg(["min", "median", "max"])

    def estimate(self, city, values):
        bounds = self.scenario_bounds(city)
        if bounds.empty or bounds.isna().any().any() or any(
            not bounds.loc["min", feature] <= values[feature] <= bounds.loc["max", feature]
            for feature in NUMERIC_FEATURES
        ) or any(values[feature] % 1 for feature in ROOM_FEATURES):
            raise ValueError("Spesifikasi di luar cakupan data latih wilayah ini.")
        features = pd.DataFrame([{"Kota": city, **values}], columns=list(FEATURES))
        return float(self.estimator.predict(features)[0])


def evaluate_models(clean):
    train_index, test_index = holdout_split(clean)
    train, test = clean.iloc[train_index], clean.iloc[test_index]
    validation = grouped_splits(train, 4)
    feature_names = list(FEATURES)
    cv_scores = []
    for name, model in candidates():
        errors = []
        for fit_idx, validate_idx in validation:
            fit, validate = train.iloc[fit_idx], train.iloc[validate_idx]
            model.fit(fit[feature_names], fit[TARGET])
            errors.append(abs(validate[TARGET].to_numpy() - model.predict(validate[feature_names])))
        fold_means = [error.mean() for error in errors]
        cv_scores.append((name, float(np.concatenate(errors).mean()), min(fold_means), max(fold_means)))

    # Choose before scoring the held-out locations. Candidate order breaks ties in favor of the baseline.
    selected = min(cv_scores, key=lambda result: result[1])[0]
    predictions = test[["Kota", "location_group", TARGET]].rename(columns={TARGET: "actual"}).copy()
    best = None
    scores = []
    for (name, model), cv_score in zip(candidates(), cv_scores, strict=True):
        model.fit(train[feature_names], train[TARGET])
        predicted = model.predict(test[feature_names])
        scores.append((*cv_score, mean_absolute_error(test[TARGET], predicted)))
        if name == selected:
            best = model
            predictions["predicted"] = predicted
    predictions["error"] = (predictions.predicted - predictions.actual).abs()
    return Evaluation(selected, best, train, predictions,
                      pd.DataFrame(scores, columns=["model", "cv_mae", "cv_min", "cv_max", "test_mae"]))
