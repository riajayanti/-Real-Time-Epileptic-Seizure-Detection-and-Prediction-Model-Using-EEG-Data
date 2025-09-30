"""
Robust validation framework that prevents data leakage and provides reliable evaluation.

FIXES:
1. Patient-independent cross-validation
2. Proper statistical testing
3. No data leakage from preprocessing
4. Realistic performance evaluation
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix
)
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
from typing import Dict, List, Tuple, Any
import logging
from scipy import stats
import warnings

try:
    from .config import Config
except ImportError:
    from config import Config

logger = logging.getLogger(__name__)

class PatientIndependentValidator:
    """
    Implements proper patient-independent validation to prevent data leakage.
    
    This is CRITICAL for medical ML - you cannot have the same patient in 
    both training and testing sets.
    """
    
    def __init__(self, random_state: int = None):
        self.random_state = random_state or Config.RANDOM_STATE
        self.results_history = []
        
    def validate_model(self, 
                      model_class,
                      patient_data: Dict[str, Tuple[np.ndarray, np.ndarray]],
                      patient_splits: Dict[str, List[str]],
                      model_params: Dict = None,
                      apply_smote: bool = True) -> Dict[str, Any]:
        """
        Perform patient-independent validation.
        
        Args:
            model_class: Sklearn-compatible model class
            patient_data: Dict mapping patient_id -> (X, y)
            patient_splits: Train/val/test patient splits
            model_params: Parameters for model initialization
            apply_smote: Whether to apply SMOTE for class balancing
            
        Returns:
            Comprehensive validation results
        """
        model_params = model_params or {}
        
        # Prepare data splits
        train_data = self._combine_patient_data(patient_data, patient_splits['train'])
        val_data = self._combine_patient_data(patient_data, patient_splits['val'])
        test_data = self._combine_patient_data(patient_data, patient_splits['test'])
        
        logger.info(f"Train: {len(patient_splits['train'])} patients, {len(train_data[0])} epochs")
        logger.info(f"Val: {len(patient_splits['val'])} patients, {len(val_data[0])} epochs")
        logger.info(f"Test: {len(patient_splits['test'])} patients, {len(test_data[0])} epochs")
        
        # Fit preprocessing on training data only
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(train_data[0])
        X_val_scaled = scaler.transform(val_data[0])
        X_test_scaled = scaler.transform(test_data[0])
        
        # Apply SMOTE only to training data
        if apply_smote:
            X_train_balanced, y_train_balanced = self._apply_smote_safely(
                X_train_scaled, train_data[1]
            )
        else:
            X_train_balanced, y_train_balanced = X_train_scaled, train_data[1]
            
        # Train model
        model = model_class(**model_params)
        model.fit(X_train_balanced, y_train_balanced)
        
        # Evaluate on all splits
        results = {}
        
        # Training performance (on balanced data)
        train_pred = model.predict(X_train_balanced)
        train_proba = model.predict_proba(X_train_balanced)[:, 1] if hasattr(model, 'predict_proba') else None
        results['train'] = self._calculate_metrics(y_train_balanced, train_pred, train_proba)
        
        # Validation performance
        val_pred = model.predict(X_val_scaled)
        val_proba = model.predict_proba(X_val_scaled)[:, 1] if hasattr(model, 'predict_proba') else None
        results['val'] = self._calculate_metrics(val_data[1], val_pred, val_proba)
        
        # Test performance (most important)
        test_pred = model.predict(X_test_scaled)
        test_proba = model.predict_proba(X_test_scaled)[:, 1] if hasattr(model, 'predict_proba') else None
        results['test'] = self._calculate_metrics(test_data[1], test_pred, test_proba)
        
        # Add metadata
        results['metadata'] = {
            'model_class': model_class.__name__,
            'model_params': model_params,
            'train_patients': patient_splits['train'],
            'val_patients': patient_splits['val'],
            'test_patients': patient_splits['test'],
            'smote_applied': apply_smote,
            'class_distribution': {
                'train_original': dict(zip(*np.unique(train_data[1], return_counts=True))),
                'train_balanced': dict(zip(*np.unique(y_train_balanced, return_counts=True))),
                'test': dict(zip(*np.unique(test_data[1], return_counts=True)))
            }
        }
        
        self.results_history.append(results)
        return results
    
    def cross_validate_patients(self,
                              model_class,
                              patient_data: Dict[str, Tuple[np.ndarray, np.ndarray]],
                              n_folds: int = 5,
                              model_params: Dict = None) -> Dict[str, Any]:
        """
        Perform patient-independent cross-validation.
        
        CRITICAL: Each fold has completely different patients.
        """
        model_params = model_params or {}
        patient_ids = list(patient_data.keys())
        
        if len(patient_ids) < n_folds:
            logger.warning(f"Only {len(patient_ids)} patients available for {n_folds}-fold CV")
            n_folds = len(patient_ids)
            
        # Create patient-based folds
        np.random.seed(self.random_state)
        shuffled_patients = np.random.permutation(patient_ids)
        
        fold_results = []
        
        for fold in range(n_folds):
            logger.info(f"Running fold {fold + 1}/{n_folds}")
            
            # Split patients for this fold
            test_start = fold * len(shuffled_patients) // n_folds
            test_end = (fold + 1) * len(shuffled_patients) // n_folds
            
            test_patients = shuffled_patients[test_start:test_end].tolist()
            train_patients = [p for p in shuffled_patients if p not in test_patients]
            
            # Further split training patients for validation
            # Ensure we don't end up with empty training set
            val_size = max(1, min(len(train_patients) // 4, len(train_patients) - 1))
            val_patients = train_patients[-val_size:]
            train_patients = train_patients[:-val_size]
            
            # Skip fold if we don't have enough patients
            if not train_patients:
                logger.warning(f"Skipping fold {fold + 1} - insufficient training patients")
                continue
            
            patient_splits = {
                'train': train_patients,
                'val': val_patients,
                'test': test_patients
            }
            
            # Validate this fold
            fold_result = self.validate_model(
                model_class, patient_data, patient_splits, model_params
            )
            fold_results.append(fold_result)
            
        # Aggregate results across folds
        if not fold_results:
            logger.warning("No valid folds completed - returning empty results")
            return {
                'n_folds': 0,
                'accuracy_mean': np.nan,
                'accuracy_std': np.nan,
                'warning': 'Insufficient data for cross-validation'
            }
        
        aggregated = self._aggregate_cv_results(fold_results)
        return aggregated
    
    def _combine_patient_data(self, patient_data: Dict, patient_ids: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """Combine data from multiple patients."""
        X_list = []
        y_list = []
        
        for patient_id in patient_ids:
            if patient_id in patient_data:
                X, y = patient_data[patient_id]
                X_list.append(X)
                y_list.append(y)
                
        if not X_list:
            raise ValueError(f"No data found for patients: {patient_ids}")
            
        X_combined = np.vstack(X_list)
        y_combined = np.concatenate(y_list)
        
        return X_combined, y_combined
    
    def _apply_smote_safely(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Apply SMOTE with proper error handling."""
        try:
            # Check if we have both classes
            unique_classes = np.unique(y)
            if len(unique_classes) < 2:
                logger.warning("Only one class present, skipping SMOTE")
                return X, y
                
            # Check if minority class has enough samples
            class_counts = dict(zip(*np.unique(y, return_counts=True)))
            min_count = min(class_counts.values())
            
            if min_count < 2:
                logger.warning("Not enough minority samples for SMOTE")
                return X, y
                
            smote = SMOTE(sampling_strategy=Config.SMOTE_RATIO, random_state=self.random_state)
            X_balanced, y_balanced = smote.fit_resample(X, y)
            
            logger.info(f"SMOTE applied: {dict(zip(*np.unique(y, return_counts=True)))} -> "
                       f"{dict(zip(*np.unique(y_balanced, return_counts=True)))}")
            
            return X_balanced, y_balanced
            
        except Exception as e:
            logger.warning(f"SMOTE failed: {e}, using original data")
            return X, y
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray, 
                          y_proba: np.ndarray = None) -> Dict[str, float]:
        """Calculate comprehensive evaluation metrics."""
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'specificity': self._calculate_specificity(y_true, y_pred),
            'n_samples': len(y_true),
            'n_positive': np.sum(y_true),
            'n_negative': len(y_true) - np.sum(y_true)
        }
        
        if y_proba is not None:
            try:
                metrics['auc'] = roc_auc_score(y_true, y_proba)
            except ValueError:
                metrics['auc'] = np.nan
                
        return metrics
    
    def _calculate_specificity(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate specificity (true negative rate)."""
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        return tn / (tn + fp) if (tn + fp) > 0 else 0.0
    
    def _aggregate_cv_results(self, fold_results: List[Dict]) -> Dict[str, Any]:
        """Aggregate cross-validation results with statistical analysis."""
        # Extract test metrics from each fold
        test_metrics = [result['test'] for result in fold_results]
        
        aggregated = {}
        
        # Calculate mean and std for each metric
        if not test_metrics:
            return {'n_folds': 0, 'warning': 'No test metrics to aggregate'}
            
        for metric in test_metrics[0].keys():
            if metric in ['n_samples', 'n_positive', 'n_negative']:
                # Sum these metrics
                values = [fold[metric] for fold in test_metrics]
                aggregated[f'{metric}_total'] = sum(values)
            else:
                # Mean and std for performance metrics
                values = [fold[metric] for fold in test_metrics if not np.isnan(fold[metric])]
                if values:
                    aggregated[f'{metric}_mean'] = np.mean(values)
                    aggregated[f'{metric}_std'] = np.std(values)
                    aggregated[f'{metric}_values'] = values
                    
                    # 95% confidence interval
                    if len(values) > 1:
                        ci = stats.t.interval(0.95, len(values)-1, 
                                            loc=np.mean(values), 
                                            scale=stats.sem(values))
                        aggregated[f'{metric}_ci'] = ci
        
        # Add fold details
        aggregated['fold_results'] = fold_results
        aggregated['n_folds'] = len(fold_results)
        
        return aggregated

class RealisticPerformanceAnalyzer:
    """
    Analyzes whether reported performance is realistic for medical ML.
    
    Flags suspicious results that might indicate data leakage or overfitting.
    """
    
    @staticmethod
    def analyze_results(results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze results for red flags.
        
        Args:
            results: Validation results dictionary
            
        Returns:
            Analysis with warnings and recommendations
        """
        analysis = {
            'red_flags': [],
            'warnings': [],
            'recommendations': [],
            'is_realistic': True
        }
        
        test_metrics = results.get('test', {})
        
        # Red flag: Perfect or near-perfect performance
        if test_metrics.get('accuracy', 0) >= 0.99:
            analysis['red_flags'].append(
                f"Suspiciously high accuracy: {test_metrics['accuracy']:.3f}"
            )
            analysis['is_realistic'] = False
            
        if test_metrics.get('auc', 0) >= 0.99:
            analysis['red_flags'].append(
                f"Suspiciously high AUC: {test_metrics['auc']:.3f}"
            )
            analysis['is_realistic'] = False
            
        # Warning: Large train-test gap
        train_metrics = results.get('train', {})
        if train_metrics and test_metrics:
            acc_gap = train_metrics.get('accuracy', 0) - test_metrics.get('accuracy', 0)
            if acc_gap > 0.1:
                analysis['warnings'].append(
                    f"Large train-test accuracy gap: {acc_gap:.3f} (possible overfitting)"
                )
                
        # Warning: Class imbalance handling
        metadata = results.get('metadata', {})
        class_dist = metadata.get('class_distribution', {})
        test_dist = class_dist.get('test', {})
        
        if test_dist:
            minority_ratio = min(test_dist.values()) / sum(test_dist.values())
            if minority_ratio < 0.05:
                analysis['warnings'].append(
                    f"Severe class imbalance in test set: {minority_ratio:.3f}"
                )
                
        # Recommendations
        if analysis['red_flags']:
            analysis['recommendations'].extend([
                "Check for data leakage between train/test sets",
                "Verify patient-independent validation",
                "Review preprocessing pipeline for future information",
                "Consider simpler baseline models"
            ])
            
        if analysis['warnings']:
            analysis['recommendations'].extend([
                "Use stratified sampling to maintain class balance",
                "Apply stronger regularization to reduce overfitting",
                "Collect more data from underrepresented class"
            ])
            
        return analysis

