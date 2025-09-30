"""
Robust EEG data processing pipeline for seizure detection.
Fixes critical issues in original implementation.
"""
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from collections import Counter
import warnings

try:
    from .config import Config
except ImportError:
    from config import Config

# Optional MNE import for EEG processing
try:
    import mne
    # Suppress MNE warnings for cleaner output
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    mne.set_log_level('ERROR')
    MNE_AVAILABLE = True
except ImportError:
    MNE_AVAILABLE = False
    mne = None

logger = logging.getLogger(__name__)

class CHBMITDataProcessor:
    """
    Robust processor for CHB-MIT database that fixes critical issues:
    1. Proper temporal alignment between epochs and labels
    2. Patient-independent data organization
    3. Robust error handling
    4. Configurable parameters
    """
    
    def __init__(self, data_root: str = None):
        self.data_root = Path(data_root) if data_root else Path(Config.DATA_ROOT)
        self.config = Config()
        
    def get_patient_files(self, patient_id: str) -> Dict[str, any]:
        """
        Get all files for a specific patient with proper organization.
        
        Args:
            patient_id: Patient identifier (e.g., 'chb01')
            
        Returns:
            Dictionary with patient info, files, and seizure annotations
        """
        patient_dir = self.data_root / patient_id
        if not patient_dir.exists():
            raise FileNotFoundError(f"Patient directory not found: {patient_dir}")
            
        # Find summary file
        summary_files = list(patient_dir.glob(f"{patient_id}-summary.txt"))
        if not summary_files:
            raise FileNotFoundError(f"Summary file not found for {patient_id}")
            
        summary_file = summary_files[0]
        
        # Parse summary file for seizure information
        seizure_info = self._parse_summary_file(summary_file)
        
        # Get all EDF files
        edf_files = sorted(list(patient_dir.glob("*.edf")))
        
        return {
            'patient_id': patient_id,
            'summary_file': summary_file,
            'edf_files': edf_files,
            'seizures': seizure_info
        }
    
    def _parse_summary_file(self, summary_file: Path) -> List[Dict]:
        """
        Parse CHB-MIT summary file to extract seizure timing information.
        
        FIXES: Proper parsing logic that handles edge cases
        """
        seizures = []
        current_file = None
        
        with open(summary_file, 'r') as f:
            lines = f.readlines()
            
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for file names
            if 'File Name:' in line:
                current_file = line.split(':')[1].strip()
                
            # Look for seizure information
            elif 'Number of Seizures in File:' in line:
                num_seizures = int(line.split(':')[1].strip())
                
                # Parse each seizure in this file
                for j in range(num_seizures):
                    i += 1
                    if i < len(lines) and 'Seizure Start Time:' in lines[i]:
                        start_time = int(lines[i].split(':')[1].strip().split()[0])
                        i += 1
                        if i < len(lines) and 'Seizure End Time:' in lines[i]:
                            end_time = int(lines[i].split(':')[1].strip().split()[0])
                            
                            seizures.append({
                                'file': current_file,
                                'start_time': start_time,
                                'end_time': end_time
                            })
            i += 1
            
        logger.info(f"Found {len(seizures)} seizures in {summary_file.name}")
        return seizures
    
    def process_patient_data(self, patient_id: str) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """
        Process all data for a single patient with proper temporal alignment.
        
        FIXES:
        1. Correct epoch-label alignment
        2. Proper handling of file boundaries
        3. Robust error handling
        """
        patient_info = self.get_patient_files(patient_id)
        all_epochs = []
        all_labels = []
        file_metadata = []
        
        for edf_file in patient_info['edf_files']:
            try:
                epochs, labels, metadata = self._process_single_file(
                    edf_file, patient_info['seizures']
                )
                
                if epochs is not None and len(epochs) > 0:
                    all_epochs.extend(epochs)
                    all_labels.extend(labels)
                    file_metadata.append(metadata)
                    
            except Exception as e:
                logger.warning(f"Failed to process {edf_file}: {e}")
                continue
                
        if not all_epochs:
            raise ValueError(f"No valid epochs found for patient {patient_id}")
            
        epochs_array = np.array(all_epochs)
        labels_array = np.array(all_labels)
        
        # Validate epoch-label alignment
        assert len(epochs_array) == len(labels_array), \
            f"Epoch-label mismatch: {len(epochs_array)} epochs, {len(labels_array)} labels"
            
        metadata = {
            'patient_id': patient_id,
            'total_epochs': len(epochs_array),
            'seizure_epochs': np.sum(labels_array),
            'files_processed': len(file_metadata),
            'file_details': file_metadata
        }
        
        logger.info(f"Patient {patient_id}: {len(epochs_array)} epochs, "
                   f"{np.sum(labels_array)} seizure epochs")
        
        return epochs_array, labels_array, metadata
    
    def _process_single_file(self, edf_file: Path, patient_seizures: List[Dict]) -> Tuple[List, List, Dict]:
        """
        Process a single EDF file with correct temporal alignment.
        
        FIXES: Proper epoch timing calculation
        """
        if not MNE_AVAILABLE:
            raise ImportError("MNE library is required for EEG file processing. Install with: pip install mne")
            
        try:
            # Load raw data
            raw = mne.io.read_raw_edf(str(edf_file), preload=True, verbose=False)
            
            # Check if required channels exist
            available_channels = set(raw.ch_names)
            required_channels = set(self.config.SELECTED_CHANNELS)
            
            missing_channels = required_channels - available_channels
            if missing_channels:
                logger.warning(f"Missing channels in {edf_file.name}: {missing_channels}")
                return None, None, None
                
            # Select channels and resample
            raw.pick_channels(self.config.SELECTED_CHANNELS)
            raw.resample(self.config.TARGET_SAMPLING_RATE)
            
            # Create epochs with proper timing
            epoch_duration = self.config.EPOCH_LENGTH
            overlap = self.config.EPOCH_OVERLAP
            step_size = epoch_duration - overlap
            
            epochs_data = []
            epoch_times = []
            
            total_duration = raw.times[-1]  # Total recording duration in seconds
            
            current_time = 0
            while current_time + epoch_duration <= total_duration:
                # Extract epoch data
                start_sample = int(current_time * self.config.TARGET_SAMPLING_RATE)
                end_sample = int((current_time + epoch_duration) * self.config.TARGET_SAMPLING_RATE)
                
                epoch_data = raw.get_data()[:, start_sample:end_sample]
                epochs_data.append(epoch_data)
                epoch_times.append((current_time, current_time + epoch_duration))
                
                current_time += step_size
            
            # Create labels with CORRECT temporal alignment
            labels = self._create_labels_for_file(
                edf_file.name, epoch_times, patient_seizures
            )
            
            # Validate alignment
            assert len(epochs_data) == len(labels), \
                f"Epoch-label mismatch in {edf_file.name}: {len(epochs_data)} vs {len(labels)}"
            
            metadata = {
                'filename': edf_file.name,
                'total_epochs': len(epochs_data),
                'seizure_epochs': sum(labels),
                'duration': total_duration,
                'channels': raw.ch_names
            }
            
            return epochs_data, labels, metadata
            
        except Exception as e:
            logger.error(f"Error processing {edf_file}: {e}")
            return None, None, None
    
    def _create_labels_for_file(self, filename: str, epoch_times: List[Tuple], 
                               patient_seizures: List[Dict]) -> List[int]:
        """
        Create labels with CORRECT temporal alignment.
        
        FIXES: Proper overlap detection between epochs and seizures
        """
        labels = []
        file_seizures = [s for s in patient_seizures if s['file'] == filename]
        
        for epoch_start, epoch_end in epoch_times:
            is_seizure = False
            
            for seizure in file_seizures:
                seizure_start = seizure['start_time']
                seizure_end = seizure['end_time']
                
                # Check for overlap (ANY overlap marks epoch as seizure)
                if epoch_start < seizure_end and epoch_end > seizure_start:
                    is_seizure = True
                    break
                    
            labels.append(1 if is_seizure else 0)
            
        return labels

class PatientIndependentSplitter:
    """
    CRITICAL FIX: Proper patient-independent validation.
    
    This ensures no data leakage between training and testing.
    """
    
    @staticmethod
    def split_patients(patient_ids: List[str], test_ratio: float = 0.2, 
                      val_ratio: float = 0.2, random_state: int = 42) -> Dict[str, List[str]]:
        """
        Split patients into train/val/test sets to prevent data leakage.
        
        Args:
            patient_ids: List of all patient IDs
            test_ratio: Fraction of patients for testing
            val_ratio: Fraction of patients for validation
            random_state: Random seed for reproducibility
            
        Returns:
            Dictionary with 'train', 'val', 'test' patient lists
        """
        np.random.seed(random_state)
        shuffled_patients = np.random.permutation(patient_ids)
        
        n_patients = len(shuffled_patients)
        n_test = max(1, int(n_patients * test_ratio))
        n_val = max(1, int(n_patients * val_ratio))
        n_train = n_patients - n_test - n_val
        
        if n_train < 1:
            raise ValueError(f"Not enough patients ({n_patients}) for proper split")
            
        train_patients = shuffled_patients[:n_train].tolist()
        val_patients = shuffled_patients[n_train:n_train + n_val].tolist()
        test_patients = shuffled_patients[n_train + n_val:].tolist()
        
        return {
            'train': train_patients,
            'val': val_patients,
            'test': test_patients
        }

