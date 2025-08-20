import sys
import os
from unittest.mock import Mock

# Add src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock Google modules that might not be available in test environment
sys.modules['google.auth'] = Mock()
sys.modules['google.auth.transport.requests'] = Mock()
sys.modules['google.oauth2.credentials'] = Mock()
sys.modules['google_auth_oauthlib.flow'] = Mock()
sys.modules['googleapiclient.discovery'] = Mock()
sys.modules['googleapiclient.errors'] = Mock()


