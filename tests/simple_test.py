"""
Simple test to verify the fixed pipeline works correctly.
Compatible with older Python versions.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np

# Test imports
try:
    from config import Config
    from data_processing import PatientIndependentSplitter
    from validation import PatientIndependentValidator, RealisticPerformanceAnalyzer
    from models import ModelFactory
    print("[OK] All imports successful")
except ImportError as e:
    print("[FAIL] Import failed: {}".format(e))
    sys.exit(1)

def test_basic_functionality():
    """Test basic functionality without complex dependencies."""
    print("Testing basic functionality...")
    
    # Test patient splitter
    patients = ['patient_01', 'patient_02', 'patient_03', 'patient_04', 'patient_05']
    splitter = PatientIndependentSplitter()
    splits = splitter.split_patients(patients, test_ratio=0.2, val_ratio=0.2, random_state=42)
    
    assert len(splits['train']) + len(splits['val']) + len(splits['test']) == len(patients)
    print("[OK] Patient splitter works")
    
    # Test model factory
    available_models = ModelFactory.get_available_models()
    assert len(available_models) > 0
    print("[OK] Model factory works")
    
    # Test creating a model
    model = ModelFactory.create_model('logistic', random_state=42)
    assert model is not None
    print("[OK] Model creation works")
    
    # Test with synthetic data
    np.random.seed(42)
    X = np.random.randn(100, 50)
    y = np.random.choice([0, 1], size=100, p=[0.8, 0.2])
    
    # Simple train/test
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    
    assert len(predictions) == len(y_test)
    print("[OK] Model training and prediction works")
    
    # Test red flag analyzer
    analyzer = RealisticPerformanceAnalyzer()
    
    # Test with perfect results (should trigger red flags)
    perfect_results = {
        'test': {'accuracy': 1.0, 'auc': 1.0},
        'train': {'accuracy': 1.0},
        'metadata': {'class_distribution': {'test': {0: 90, 1: 10}}}
    }
    
    analysis = analyzer.analyze_results(perfect_results)
    assert not analysis['is_realistic']
    assert len(analysis['red_flags']) > 0
    print("[OK] Red flag detection works")
    
    print("\n[SUCCESS] All basic tests passed!")

if __name__ == "__main__":
    print("Running simplified pipeline tests...")
    print("=" * 50)
    
    try:
        test_basic_functionality()
        print("\n[SUCCESS] Pipeline is working correctly!")
        print("\nTo run with real data:")
        print("1. Set Config.DATA_ROOT to your CHB-MIT dataset path")
        print("2. Run: python main.py")
        
    except Exception as e:
        print("\n[FAIL] Test failed: {}".format(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)
