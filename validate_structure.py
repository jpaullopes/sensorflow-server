#!/usr/bin/env python3
"""
Validation script to check if the modular structure is working correctly.
"""

def validate_structure():
    try:
        print("🔍 Validating modular structure...")
        
        # Test main imports
        from src.config import app_state
        from src.logger_config import setup_logger
        from src.models import TemperatureReadingPayload, DataDB
        from src.database import get_db
        from src.auth import verify_api_key
        from src.websocket_manager import manager
        from src.routes import api_router, websocket_router
        
        print("✅ All module imports successful!")
        print("✅ Modular structure is working correctly!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = validate_structure()
    exit(0 if success else 1)
