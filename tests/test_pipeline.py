"""
Quick test to verify the fixed pipeline works correctly.
Run this to validate the implementation.
"""
import numpy as np
import tempfile
from pathlib import Path
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config
from data_processing import PatientIndependentSplitter
from validation import PatientIndependentValidator, RealisticPerformanceAnalyzer
from models import ModelFactory


def test_patient_splitter():
    """Test patient-independent splitting logic."""
    patients = ['patient_01', 'patient_02', 'patient_03', 'patient_04', 'patient_05']
    
    splitter = PatientIndependentSplitter()
    splits = splitter.split_patients(patients, test_ratio=0.2, val_ratio=0.2)
    
    # Check that all patients are assigned
    all_assigned = set(splits['train'] + splits['val'] + splits['test'])
    assert all_assigned == set(patients)
    
    # Check that splits don't overlap
    train_set = set(splits['train'])
    val_set = set(splits['val'])
    test_set = set(splits['test'])
    
    assert len(train_set & val_set) == 0
    assert len(train_set & test_set) == 0
    assert len(val_set & test_set) == 0


def test_model_factory():
    """Test model creation and interfaces."""
    # Test all available models can be created
    available_models = ModelFactory.get_available_models()
    
    for model_name, model_class in available_models.items():
        model = ModelFactory.create_model(model_name, random_state=42)
        assert model is not None
        assert hasattr(model, 'fit')
        assert hasattr(model, 'predict')


def test_synthetic_validation():
    """Test validation pipeline with synthetic data."""
    # Create synthetic patient data
    np.random.seed(42)
    
    patient_data = {}
    for i in range(5):
        patient_id = 'test_patient_{:02d}'.format(i)
        
        # Small dataset for quick testing
        n_epochs = 50
        n_features = 100
        
        X = np.random.randn(n_epochs, n_features)
        y = np.random.choice([0, 1], size=n_epochs, p=[0.9, 0.1])  # 10% seizures
        
        patient_data[patient_id] = (X, y)
    
    # Test patient splitting
    splitter = PatientIndependentSplitter()
    patient_splits = splitter.split_patients(
        list(patient_data.keys()),
        test_ratio=0.2,
        val_ratio=0.2,
        random_state=42
    )
    
    # Test validation
    validator = PatientIndependentValidator(random_state=42)
    
    # Test with a simple model
    model_class = ModelFactory.get_available_models()['logistic']
    results = validator.validate_model(
        model_class=model_class,
        patient_data=patient_data,
        patient_splits=patient_splits,
        apply_smote=False  # Skip SMOTE for quick test
    )
    
    # Check that results have expected structure
    assert 'train' in results
    assert 'val' in results
    assert 'test' in results
    assert 'metadata' in results
    
    # Check that test metrics are present
    test_metrics = results['test']
    required_metrics = ['accuracy', 'precision', 'recall', 'f1']
    
    for metric in required_metrics:
        assert metric in test_metrics
        assert 0 <= test_metrics[metric] <= 1


def test_red_flag_detection():
    """Test red flag detection for suspicious results."""
    analyzer = RealisticPerformanceAnalyzer()
    
    # Test perfect performance (should trigger red flags)
    suspicious_results = {
        'test': {
            'accuracy': 1.0,
            'auc': 1.0,
            'precision': 1.0,
            'recall': 1.0
        },
        'train': {
            'accuracy': 1.0
        },
        'metadata': {
            'class_distribution': {
                'test': {0: 90, 1: 10}
            }
        }
    }
    
    analysis = analyzer.analyze_results(suspicious_results)
    
    assert not analysis['is_realistic']
    assert len(analysis['red_flags']) > 0
    assert 'accuracy' in str(analysis['red_flags']).lower()


def test_realistic_performance():
    """Test that realistic performance doesn't trigger red flags."""
    analyzer = RealisticPerformanceAnalyzer()
    
    # Test realistic performance
    realistic_results = {
        'test': {
            'accuracy': 0.85,
            'auc': 0.82,
            'precision': 0.65,
            'recall': 0.78
        },
        'train': {
            'accuracy': 0.87
        },
        'metadata': {
            'class_distribution': {
                'test': {0: 90, 1: 10}
            }
        }
    }
    
    analysis = analyzer.analyze_results(realistic_results)
    
    # Should not trigger major red flags
    assert analysis['is_realistic']


if __name__ == "__main__":
    print("Running pipeline validation tests...")
    print("=" * 50)
    
    try:
        test_patient_splitter()
        print("✅ Patient splitter test passed")
        
        test_model_factory()
        print("✅ Model factory test passed")
        
        test_synthetic_validation()
        print("✅ Synthetic validation test passed")
        
        test_red_flag_detection()
        print("✅ Red flag detection test passed")
        
        test_realistic_performance()
        print("✅ Realistic performance test passed")
        
        print("\n🎉 All tests passed! Pipeline is working correctly.")
        
    except Exception as e:
        print("❌ Test failed: {}".format(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)
