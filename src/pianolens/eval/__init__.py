"""pianolens.eval: grouped splits, metrics, cluster bootstrap, rater parity, Bradley-Terry.

Generic on purpose: everything takes numpy / pandas arrays plus group labels, so it does not
depend on the dataset types in ``pianolens.data``.
"""

from .bootstrap import BootstrapResult, bootstrap_ci, bootstrap_indices, paired_bootstrap_diff
from .bradley_terry import BradleyTerry, fit_bradley_terry
from .metrics import METRICS, kendall, pairwise_accuracy, pearson, r2, spearman
from .rater_parity import RaterParity, loo_means, rater_parity, ratings_matrix
from .splits import check_disjoint, group_fold_ids, group_kfold

__all__ = [
    "METRICS",
    "BootstrapResult",
    "BradleyTerry",
    "RaterParity",
    "bootstrap_ci",
    "bootstrap_indices",
    "check_disjoint",
    "fit_bradley_terry",
    "group_fold_ids",
    "group_kfold",
    "kendall",
    "loo_means",
    "paired_bootstrap_diff",
    "pairwise_accuracy",
    "pearson",
    "r2",
    "rater_parity",
    "ratings_matrix",
    "spearman",
]
