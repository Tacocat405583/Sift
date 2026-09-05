import mlflow
import pandas as pd
from sklearn  import datasets
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics  import  accuracy_score,  precision_score, recall_score, f1_score

#point at the server started with: mlflow server --port 5000
mlflow.set_tracking_uri("http://127.0.0.1:5000")

mlflow.set_experiment("MLflow Quickstart")

#Load Iris dataset
X,y = datasets.load_iris(return_X_y=True)

#Split into training and test sets
X_train,X_test,y_train,y_test = train_test_split(X,y,test_size=.2,random_state=42)

#Define model hyperparameters

params = {
    "solver":"lbfgs",
    "max_iter":1000,
    "random_state":8888,
}

#enable autologging for scikit-learn

mlflow.sklearn.autolog()

#just train model normally
lr = LogisticRegression(**params)
lr.fit(X_train, y_train)
