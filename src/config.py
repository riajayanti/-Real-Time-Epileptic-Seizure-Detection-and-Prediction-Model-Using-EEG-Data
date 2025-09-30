"""
Configuration file for seizure detection project.
"""
import os
from pathlib import Path

class Config:
    """Configuration settings for the seizure detection project."""
    
    # Data paths - CONFIGURABLE, not hard-coded
    DATA_ROOT = os.getenv('CHB_MIT_DATA_PATH', '/path/to/chb-mit/data')
    OUTPUT_DIR = Path('outputs')
    MODELS_DIR = Path('models')
    LOGS_DIR = Path('logs')
    
    # EEG Processing parameters
    SAMPLING_RATE = 256  # Original CHB-MIT sampling rate
    TARGET_SAMPLING_RATE = 64  # Downsampled rate
    EPOCH_LENGTH = 20  # seconds
    EPOCH_OVERLAP = 4   # seconds
    
    # Channel selection - standardized 10-20 system
    SELECTED_CHANNELS = [
        'FP1-F7', 'F7-T7', 'T7-P7', 'P7-O1', 'FP1-F3',
        'F3-C3', 'C3-P3', 'P3-O1', 'FP2-F4', 'F4-C4'
    ]
    
    # Model parameters
    RANDOM_STATE = 42
    TEST_SIZE = 0.2
    VALIDATION_SIZE = 0.2
    
    # Cross-validation strategy
    N_FOLDS = 5
    
    # Class imbalance handling
    SMOTE_RATIO = 0.5
    
    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist."""
        for directory in [cls.OUTPUT_DIR, cls.MODELS_DIR, cls.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

