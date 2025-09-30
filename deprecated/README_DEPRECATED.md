# ⚠️ DEPRECATED CODE - DO NOT USE

This directory contains the **original broken implementation** that has been replaced with a scientifically sound version.

## 🚨 Why This Code is Deprecated

### Critical Scientific Flaws
- **Data Leakage**: Same patients in training and testing sets
- **Impossible Claims**: 100% accuracy (indicates fundamental validation errors)
- **Temporal Misalignment**: Epoch timing didn't match seizure annotations
- **No Patient Independence**: Violates basic medical ML principles

### Code Quality Issues  
- **981-line monolithic file**: Unmaintainable spaghetti code
- **Hard-coded paths**: Non-reproducible Google Drive dependencies
- **No error handling**: Crashes on edge cases
- **Poor documentation**: Unclear methodology

## ✅ What to Use Instead

Use the **main project directory** which contains:
- Proper patient-independent validation
- Realistic performance expectations (75-92% accuracy)
- Clean, modular architecture
- Robust error handling
- Comprehensive documentation

## 📚 Educational Value

This deprecated code serves as an example of:
- How NOT to implement medical ML
- Common pitfalls in seizure detection research
- Why 100% accuracy claims are red flags
- The importance of proper validation methodology

**For any serious research or application, use only the main implementation.**

