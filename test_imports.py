# test_imports.py
"""
Test script to verify all imports are working correctly.
"""

try:
    print("Testing imports...")
    
    print("✓ Importing config...")
    from config import app_state, EXPECTED_API_KEY, EXPECTED_API_KEY_WS, MAX_WS_CONNECTIONS_PER_KEY
    
    print("✓ Importing logger_config...")
    from logger_config import setup_logger
    
    print("✓ Importing models...")
    from models import TemperatureReadingPayload, TemperatureDataResponse, DataDB, Base
    
    print("✓ Importing database...")
    from database import initialize_database, get_db
    
    print("✓ Importing auth...")
    from auth import verify_api_key, verify_websocket_api_key
    
    print("✓ Importing websocket_manager...")
    from websocket_manager import manager, ConnectionManager
    
    print("✓ Importing routes...")
    from routes import api_router, websocket_router
    
    print("\n🎉 All imports successful! The modularization is working correctly.")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
