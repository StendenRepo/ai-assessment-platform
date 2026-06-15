# Project Report — Customer Churn Prediction

## Data Preparation
We cleaned the raw customer dataset by removing duplicate records, handling
missing values with median imputation, and normalising the numeric features so
they share a common scale. Categorical fields were encoded before training.

## Exploratory Analysis
We carried out exploratory data analysis and produced clear visualisations,
including histograms, correlation heatmaps, and box plots, to understand the
distribution of the features and how they relate to customer churn.

## Modelling and Evaluation
We trained several machine learning models, including logistic regression and a
random forest, and evaluated them with accuracy, precision, recall, and the F1
score using cross-validation to compare their performance fairly.

## Reproducibility
The whole project is documented in a README with the exact steps to reproduce
our results, the dependency versions are pinned, and a fixed random seed makes
every run repeatable.

## Future Work
We would like to test additional feature engineering ideas and gather more
recent data in a later iteration.
