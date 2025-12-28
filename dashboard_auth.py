"""
Dashboard Authentication Module
Secure login with hashed passwords using bcrypt.
"""
import json
import hashlib
import secrets
import time
from pathlib import Path
from typing import Optional, Dict

# Try to import bcrypt, fall back to hashlib if not available
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("[AUTH] Warning: bcrypt not installed, using hashlib fallback")

USERS_FILE = Path(__file__).parent / "dashboard_users.json"


class DashboardAuth:
    """
    Secure authentication for dashboard access.
    
    Features:
    - Password hashing with bcrypt (or hashlib fallback)
    - Session-based login via Streamlit
    - Multiple user support
    - Role-based access (admin, operator, viewer)
    """
    
    def __init__(self):
        self.users = self._load_users()
        
        # Create default admin if no users exist
        if not self.users:
            self._create_default_users()
    
    def _load_users(self) -> Dict:
        """Load users from JSON file."""
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[AUTH] Error loading users: {e}")
                return {}
        return {}
    
    def _save_users(self) -> None:
        """Save users to JSON file."""
        try:
            with open(USERS_FILE, 'w') as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            print(f"[AUTH] Error saving users: {e}")
    
    def _create_default_users(self) -> None:
        """Create default admin and operator users."""
        # Generate random passwords for security
        admin_pass = "admin123"  # Default password - CHANGE THIS!
        operator_pass = "operator123"  # Default password - CHANGE THIS!
        
        self.users = {
            "admin": {
                "password_hash": self.hash_password(admin_pass),
                "role": "admin",
                "name": "Administrator",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "operator": {
                "password_hash": self.hash_password(operator_pass),
                "role": "operator",
                "name": "Operator",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        self._save_users()
        print("[AUTH] Created default users (admin/admin123, operator/operator123)")
        print("[AUTH] ⚠️  IMPORTANT: Change default passwords immediately!")
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt or hashlib fallback."""
        if BCRYPT_AVAILABLE:
            return bcrypt.hashpw(
                password.encode('utf-8'), 
                bcrypt.gensalt()
            ).decode('utf-8')
        else:
            # Fallback to SHA-256 with salt
            salt = secrets.token_hex(16)
            hash_obj = hashlib.sha256((salt + password).encode('utf-8'))
            return f"sha256${salt}${hash_obj.hexdigest()}"
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        if BCRYPT_AVAILABLE and hashed.startswith("$2"):
            try:
                return bcrypt.checkpw(
                    password.encode('utf-8'), 
                    hashed.encode('utf-8')
                )
            except Exception:
                return False
        elif hashed.startswith("sha256$"):
            # Hashlib fallback verification
            parts = hashed.split("$")
            if len(parts) == 3:
                salt = parts[1]
                stored_hash = parts[2]
                hash_obj = hashlib.sha256((salt + password).encode('utf-8'))
                return hash_obj.hexdigest() == stored_hash
        return False
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        Authenticate user.
        
        Args:
            username: Username to authenticate
            password: Password to verify
            
        Returns:
            User data dict if authenticated, None otherwise
        """
        user = self.users.get(username)
        if user and self.verify_password(password, user.get('password_hash', '')):
            return {
                'username': username,
                'role': user.get('role', 'viewer'),
                'name': user.get('name', username)
            }
        return None
    
    def add_user(self, username: str, password: str, 
                 role: str = 'viewer', name: str = None) -> bool:
        """
        Add new user.
        
        Args:
            username: Username (unique)
            password: Plain text password (will be hashed)
            role: User role (admin, operator, viewer)
            name: Display name
            
        Returns:
            True if added successfully, False if user exists
        """
        if username in self.users:
            return False
        
        self.users[username] = {
            'password_hash': self.hash_password(password),
            'role': role,
            'name': name or username,
            'created_at': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self._save_users()
        return True
    
    def change_password(self, username: str, new_password: str) -> bool:
        """
        Change user password.
        
        Args:
            username: Username
            new_password: New password (will be hashed)
            
        Returns:
            True if changed, False if user not found
        """
        if username not in self.users:
            return False
        
        self.users[username]['password_hash'] = self.hash_password(new_password)
        self.users[username]['password_changed_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_users()
        return True
    
    def delete_user(self, username: str) -> bool:
        """Delete a user."""
        if username not in self.users:
            return False
        
        del self.users[username]
        self._save_users()
        return True
    
    def list_users(self) -> Dict:
        """List all users (without password hashes)."""
        return {
            username: {
                'role': data.get('role', 'viewer'),
                'name': data.get('name', username),
                'created_at': data.get('created_at', 'Unknown')
            }
            for username, data in self.users.items()
        }


def check_authentication(st) -> bool:
    """
    Check if user is authenticated.
    
    Args:
        st: Streamlit module
        
    Returns:
        True if authenticated
    """
    return st.session_state.get('authenticated', False)


def get_current_user(st) -> Optional[Dict]:
    """
    Get current logged-in user.
    
    Args:
        st: Streamlit module
        
    Returns:
        User data dict or None
    """
    return st.session_state.get('user')


def logout(st) -> None:
    """
    Log out current user.
    
    Args:
        st: Streamlit module
    """
    st.session_state['authenticated'] = False
    st.session_state['user'] = None


def login_page(st) -> bool:
    """
    Render login page and handle authentication.
    
    Args:
        st: Streamlit module
        
    Returns:
        True if user just logged in successfully
    """
    # Custom CSS for login page
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 50px auto;
        padding: 40px;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .login-header {
        text-align: center;
        margin-bottom: 30px;
    }
    .login-header h1 {
        color: #FF4B4B;
        font-size: 2em;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("## 🔐 Operator Dashboard")
        st.markdown("### Login Required")
        st.markdown("---")
        
        username = st.text_input("Username", key="login_username", 
                                 placeholder="Enter username")
        password = st.text_input("Password", type="password", key="login_password",
                                 placeholder="Enter password")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            login_clicked = st.button("🔓 Login", type="primary", use_container_width=True)
        
        if login_clicked:
            if username and password:
                auth = DashboardAuth()
                user = auth.authenticate(username, password)
                
                if user:
                    st.session_state['authenticated'] = True
                    st.session_state['user'] = user
                    st.success(f"✅ Welcome, {user['name']}!")
                    time.sleep(0.5)
                    st.rerun()
                    return True
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.warning("⚠️ Please enter username and password")
        
        st.markdown("---")
        st.caption("🔒 Secure access only. Contact admin for credentials.")
        
        # Show default credentials hint (remove in production!)
        with st.expander("ℹ️ Default Credentials (Development Only)"):
            st.code("admin / admin123\noperator / operator123")
            st.warning("⚠️ Change these passwords immediately in production!")
    
    return False
