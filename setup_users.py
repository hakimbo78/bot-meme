"""
User Management CLI for Dashboard
Run: python setup_users.py <action> [options]

Examples:
    python setup_users.py add -u newuser -p password123 -r operator -n "New User"
    python setup_users.py change-password -u admin -p newpassword
    python setup_users.py delete -u olduser
    python setup_users.py list
"""
import argparse
import sys
import getpass

from dashboard_auth import DashboardAuth


def main():
    parser = argparse.ArgumentParser(
        description='Dashboard User Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Add user:      python setup_users.py add -u john -p secret123 -r operator
  Change pass:   python setup_users.py change-password -u john -p newsecret
  Delete user:   python setup_users.py delete -u john
  List users:    python setup_users.py list
        """
    )
    
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')
    
    # Add user command
    add_parser = subparsers.add_parser('add', help='Add a new user')
    add_parser.add_argument('-u', '--username', required=True, help='Username')
    add_parser.add_argument('-p', '--password', help='Password (prompted if not provided)')
    add_parser.add_argument('-r', '--role', default='operator', 
                           choices=['admin', 'operator', 'viewer'],
                           help='User role (default: operator)')
    add_parser.add_argument('-n', '--name', help='Display name')
    
    # Change password command
    pwd_parser = subparsers.add_parser('change-password', help='Change user password')
    pwd_parser.add_argument('-u', '--username', required=True, help='Username')
    pwd_parser.add_argument('-p', '--password', help='New password (prompted if not provided)')
    
    # Delete user command
    del_parser = subparsers.add_parser('delete', help='Delete a user')
    del_parser.add_argument('-u', '--username', required=True, help='Username to delete')
    del_parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation')
    
    # List users command
    subparsers.add_parser('list', help='List all users')
    
    args = parser.parse_args()
    
    if not args.action:
        parser.print_help()
        sys.exit(1)
    
    auth = DashboardAuth()
    
    if args.action == 'add':
        # Get password if not provided
        password = args.password
        if not password:
            password = getpass.getpass("Enter password: ")
            password_confirm = getpass.getpass("Confirm password: ")
            if password != password_confirm:
                print("❌ Passwords do not match")
                sys.exit(1)
        
        if auth.add_user(args.username, password, args.role, args.name):
            print(f"✅ User '{args.username}' created successfully")
            print(f"   Role: {args.role}")
            print(f"   Name: {args.name or args.username}")
        else:
            print(f"❌ User '{args.username}' already exists")
            sys.exit(1)
    
    elif args.action == 'change-password':
        # Get password if not provided
        password = args.password
        if not password:
            password = getpass.getpass("Enter new password: ")
            password_confirm = getpass.getpass("Confirm new password: ")
            if password != password_confirm:
                print("❌ Passwords do not match")
                sys.exit(1)
        
        if auth.change_password(args.username, password):
            print(f"✅ Password changed for '{args.username}'")
        else:
            print(f"❌ User '{args.username}' not found")
            sys.exit(1)
    
    elif args.action == 'delete':
        if not args.force:
            confirm = input(f"Are you sure you want to delete '{args.username}'? (y/N): ")
            if confirm.lower() != 'y':
                print("Cancelled")
                sys.exit(0)
        
        if auth.delete_user(args.username):
            print(f"✅ User '{args.username}' deleted")
        else:
            print(f"❌ User '{args.username}' not found")
            sys.exit(1)
    
    elif args.action == 'list':
        users = auth.list_users()
        if users:
            print("\n📋 Dashboard Users:")
            print("-" * 50)
            for username, data in users.items():
                role_icon = {"admin": "👑", "operator": "🔧", "viewer": "👁️"}.get(data['role'], "")
                print(f"  {role_icon} {username}")
                print(f"     Role: {data['role']}")
                print(f"     Name: {data['name']}")
                print(f"     Created: {data['created_at']}")
                print()
        else:
            print("No users found")


if __name__ == '__main__':
    main()
