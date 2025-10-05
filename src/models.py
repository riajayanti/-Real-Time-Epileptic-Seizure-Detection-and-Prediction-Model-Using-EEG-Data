"""
Proper implementation of seizure detection models with robust evaluation.

FIXES:
1. Consistent train/test splits
2. Proper hyperparameter tuning
3. No data leakage in model selection
4. Realistic performance expectations
"""
import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.model_selection import GridSearchCV
from sklearn.base import BaseEstimator, ClassifierMixin
from typing import Dict, Any, Optional
import logging

try:
    from .config import Config
except ImportError:
    from config import Config

logger = logging.getLogger(__name__)

class SeizureDetectionModel(BaseEstimator, ClassifierMixin):
    """
    Base class for seizure detection models with consistent interface.
    """
    
    def __init__(self, random_state: int = None):
        self.random_state = random_state or Config.RANDOM_STATE
        self.model = None
        self.is_fitted = False
        
    def fit(self, X: np.ndarray, y: np.ndarray):
        """Fit the model to training data."""
        self.model.fit(X, y)
        self.is_fitted = True
        return self
        
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        return self.model.predict(X)
        
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities if supported."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X)
        else:
            # For models without predict_proba, use decision function
            if hasattr(self.model, 'decision_function'):
                scores = self.model.decision_function(X)
                # Convert to probabilities using sigmoid
                proba_pos = 1 / (1 + np.exp(-scores))
                return np.column_stack([1 - proba_pos, proba_pos])
            else:
                raise NotImplementedError("Model doesn't support probability prediction")

class ImprovedKNNClassifier(SeizureDetectionModel):
    """
    Improved K-Nearest Neighbors with proper hyperparameter selection.
    
    FIXES: Consistent validation, proper parameter tuning
    """
    
    def __init__(self, n_neighbors: int = 7, weights: str = 'uniform', 
                 metric: str = 'euclidean', random_state: int = None):
        super().__init__(random_state)
        self.n_neighbors = n_neighbors
        self.weights = weights
        self.metric = metric
        
        self.model = KNeighborsClassifier(
            n_neighbors=n_neighbors,
            weights=weights,
            metric=metric
        )
        
    @classmethod
    def with_hyperparameter_tuning(cls, X_train: np.ndarray, y_train: np.ndarray,
                                  cv: int = 5, random_state: int = None):
        """
        Create KNN with optimized hyperparameters using grid search.
        """
        param_grid = {
            'n_neighbors': [3, 5, 7, 9, 11],
            'weights': ['uniform', 'distance'],
            'metric': ['euclidean', 'manhattan', 'minkowski']
        }
        
        base_model = KNeighborsClassifier()
        grid_search = GridSearchCV(
            base_model, param_grid, cv=cv, 
            scoring='f1', n_jobs=-1, verbose=0
        )
        
        grid_search.fit(X_train, y_train)
        best_params = grid_search.best_params_
        
        logger.info(f"Best KNN parameters: {best_params}")
        
        return cls(random_state=random_state, **best_params)

class ImprovedLogisticRegression(SeizureDetectionModel):
    """
    Improved Logistic Regression with proper regularization.
    
    FIXES: Proper regularization, class balancing, convergence
    """
    
    def __init__(self, C: float = 1.0, class_weight: str = 'balanced',
                 max_iter: int = 2000, random_state: int = None):
        super().__init__(random_state)
        self.C = C
        self.class_weight = class_weight
        self.max_iter = max_iter
        
        self.model = LogisticRegression(
            C=C,
            class_weight=class_weight,
            max_iter=max_iter,
            random_state=self.random_state,
            solver='liblinear'  # Better for small datasets
        )
        
    @classmethod
    def with_hyperparameter_tuning(cls, X_train: np.ndarray, y_train: np.ndarray,
                                  cv: int = 5, random_state: int = None):
        """Create Logistic Regression with optimized hyperparameters."""
        param_grid = {
            'C': [0.001, 0.01, 0.1, 1.0, 10.0, 100.0],
            'class_weight': ['balanced', None],
            'solver': ['liblinear', 'lbfgs']
        }
        
        base_model = LogisticRegression(
            max_iter=2000,
            random_state=random_state
        )
        
        grid_search = GridSearchCV(
            base_model, param_grid, cv=cv,
            scoring='f1', n_jobs=-1, verbose=0
        )
        
        grid_search.fit(X_train, y_train)
        best_params = grid_search.best_params_
        
        logger.info(f"Best Logistic Regression parameters: {best_params}")
        
        # Filter out parameters that aren't valid for our constructor
        valid_params = {k: v for k, v in best_params.items() 
                       if k in ['C', 'class_weight']}
        return cls(random_state=random_state, **valid_params)

class ImprovedRandomForest(SeizureDetectionModel):
    """
    Improved Random Forest with proper parameter tuning and overfitting prevention.
    
    FIXES: Reasonable tree count, max_depth to prevent overfitting
    """
    
    def __init__(self, n_estimators: int = 100, max_depth: int = 10,
                 min_samples_split: int = 5, min_samples_leaf: int = 2,
                 class_weight: str = 'balanced', random_state: int = None):
        super().__init__(random_state)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.class_weight = class_weight
        
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            class_weight=class_weight,
            random_state=self.random_state,
            n_jobs=-1
        )
        
    @classmethod
    def with_hyperparameter_tuning(cls, X_train: np.ndarray, y_train: np.ndarray,
                                  cv: int = 5, random_state: int = None):
        """Create Random Forest with optimized hyperparameters."""
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [5, 10, 15, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'class_weight': ['balanced', 'balanced_subsample']
        }
        
        base_model = RandomForestClassifier(
            random_state=random_state,
            n_jobs=-1
        )
        
        # Use smaller parameter grid for efficiency
        reduced_param_grid = {
            'n_estimators': [50, 100],
            'max_depth': [10, 15],
            'min_samples_split': [5, 10],
            'class_weight': ['balanced']
        }
        
        grid_search = GridSearchCV(
            base_model, reduced_param_grid, cv=cv,
            scoring='f1', n_jobs=-1, verbose=0
        )
        
        grid_search.fit(X_train, y_train)
        best_params = grid_search.best_params_
        
        logger.info(f"Best Random Forest parameters: {best_params}")
        
        return cls(random_state=random_state, **best_params)

class ImprovedSVM(SeizureDetectionModel):
    """
    Improved SVM with proper kernel selection and regularization.
    
    FIXES: Reasonable C values, gamma selection, probability estimation
    """
    
    def __init__(self, C: float = 1.0, kernel: str = 'rbf', gamma: str = 'scale',
                 class_weight: str = 'balanced', probability: bool = True,
                 random_state: int = None):
        super().__init__(random_state)
        self.C = C
        self.kernel = kernel
        self.gamma = gamma
        self.class_weight = class_weight
        self.probability = probability
        
        self.model = SVC(
            C=C,
            kernel=kernel,
            gamma=gamma,
            class_weight=class_weight,
            probability=probability,
            random_state=self.random_state
        )
        
    @classmethod
    def with_hyperparameter_tuning(cls, X_train: np.ndarray, y_train: np.ndarray,
                                  cv: int = 5, random_state: int = None):
        """Create SVM with optimized hyperparameters."""
        # Reduced parameter grid for reasonable training time
        param_grid = {
            'C': [0.1, 1.0, 10.0],
            'kernel': ['rbf', 'linear'],
            'gamma': ['scale', 'auto'],
            'class_weight': ['balanced']
        }
        
        base_model = SVC(
            probability=True,
            random_state=random_state
        )
        
        grid_search = GridSearchCV(
            base_model, param_grid, cv=cv,
            scoring='f1', n_jobs=-1, verbose=0
        )
        
        grid_search.fit(X_train, y_train)
        best_params = grid_search.best_params_
        
        logger.info(f"Best SVM parameters: {best_params}")
        
        return cls(random_state=random_state, **best_params)

class ModelFactory:
    """
    Factory class for creating and configuring seizure detection models.
    """
    
    @staticmethod
    def get_available_models() -> Dict[str, type]:
        """Get dictionary of available model classes."""
        return {
            'knn': ImprovedKNNClassifier,
            'logistic': ImprovedLogisticRegression,
            'random_forest': ImprovedRandomForest,
            'svm': ImprovedSVM
        }
    
    @staticmethod
    def create_model(model_name: str, **kwargs) -> SeizureDetectionModel:
        """
        Create a model instance by name.
        
        Args:
            model_name: Name of the model ('knn', 'logistic', 'random_forest', 'svm')
            **kwargs: Additional parameters for model initialization
            
        Returns:
            Initialized model instance
        """
        models = ModelFactory.get_available_models()
        
        if model_name not in models:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(models.keys())}")
            
        model_class = models[model_name]
        return model_class(**kwargs)
    
    @staticmethod
    def create_tuned_model(model_name: str, X_train: np.ndarray, y_train: np.ndarray,
                          cv: int = 5, **kwargs) -> SeizureDetectionModel:
        """
        Create a model with hyperparameter tuning.
        
        Args:
            model_name: Name of the model
            X_train: Training features
            y_train: Training labels
            cv: Number of cross-validation folds for tuning
            **kwargs: Additional parameters
            
        Returns:
            Model with tuned hyperparameters
        """
        models = ModelFactory.get_available_models()
        
        if model_name not in models:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(models.keys())}")
            
        model_class = models[model_name]
        
        # Check if the model supports hyperparameter tuning
        if hasattr(model_class, 'with_hyperparameter_tuning'):
            return model_class.with_hyperparameter_tuning(X_train, y_train, cv=cv, **kwargs)
        else:
            logger.warning(f"Model {model_name} doesn't support automated tuning")
            return model_class(**kwargs)

# Utility functions for model comparison
def compare_models(patient_data: Dict, patient_splits: Dict, validator) -> pd.DataFrame:
    """
    Compare all available models using proper validation.
    
    Args:
        patient_data: Dictionary mapping patient_id -> (X, y)
        patient_splits: Train/val/test patient splits
        validator: PatientIndependentValidator instance
        
    Returns:
        DataFrame with model comparison results
    """
    models_to_test = [
        ('KNN', 'knn'),
        ('Logistic Regression', 'logistic'),
        ('Random Forest', 'random_forest'),
        ('SVM', 'svm')
    ]
    
    results = []
    
    for model_display_name, model_name in models_to_test:
        logger.info(f"Evaluating {model_display_name}...")
        
        try:
            model_class = ModelFactory.get_available_models()[model_name]
            
            # Perform validation
            result = validator.validate_model(
                model_class=model_class,
                patient_data=patient_data,
                patient_splits=patient_splits
            )
            
            # Extract test metrics
            test_metrics = result['test']
            
            results.append({
                'Model': model_display_name,
                'Accuracy': test_metrics.get('accuracy', np.nan),
                'Precision': test_metrics.get('precision', np.nan),
                'Recall': test_metrics.get('recall', np.nan),
                'F1-Score': test_metrics.get('f1', np.nan),
                'Specificity': test_metrics.get('specificity', np.nan),
                'AUC': test_metrics.get('auc', np.nan),
                'Test_Samples': test_metrics.get('n_samples', 0),
                'Seizure_Samples': test_metrics.get('n_positive', 0)
            })
            
        except Exception as e:
            logger.error(f"Failed to evaluate {model_display_name}: {e}")
            results.append({
                'Model': model_display_name,
                'Error': str(e)
            })
    
    return pd.DataFrame(results)

