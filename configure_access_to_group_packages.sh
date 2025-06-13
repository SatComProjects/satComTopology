#!/bin/bash

# ==============================================================================
# GitLab Private PyPI Registry Local Setup Script (using Personal Access Token & Group-Level Access)
# ==============================================================================
# This script automates the setup of local access to a GitLab private PyPI
# package registry using your Personal Access Token. It will:
# 1. Prompt for your GitLab Username and Personal Access Token.
# 2. Configure your ~/.netrc file for secure credential storage.
# 3. Configure your ~/.config/pip/pip.conf to use the GROUP-LEVEL package registry.
#    This allows access to all packages within the specified GitLab group.
# 4. Attempt to activate a virtual environment (if found) or guide you to create one.
# 5. Run 'pip install -r requirements.txt' to install your project's dependencies.
#
# IMPORTANT SECURITY NOTES:
# - This script uses your Personal Access Token, which grants access to ALL
#   resources your GitLab user can access. Treat it with extreme care.
# - This script creates/modifies sensitive files (.netrc). Ensure your system
#   is secure and treat your PAT as a password.
# - The .netrc file will have strict permissions (read/write only by owner).
# - NEVER commit the .netrc file to your Git repository!
# ==============================================================================

# --- Configuration ---
# Replace with the actual domain of your GitLab instance
GITLAB_HOST="gitlab.isae-supaero.fr"
# IMPORTANT: Replace with the actual NUMERICAL ID of your GitLab Group (e.g., 'eqospace').
# You can find this ID on your group's main page or in its URL in GitLab.
GITLAB_GROUP_ID="3310"

# Construct the full Group-Level PyPI simple index URL
PRIVATE_PYPI_URL="https://${GITLAB_HOST}/api/v4/groups/${GITLAB_GROUP_ID}/-/packages/pypi/simple"

# --- Functions ---

# Function to safely get input without echoing for password
get_secret_input() {
    local prompt_message="$1"
    local var_name="$2"
    printf "%s" "$prompt_message"
    read -s "$var_name"
    echo # New line after silent input
}

# --- Main Script ---

echo "==============================================="
echo " GitLab Group PyPI Registry Setup (using PAT) "
echo "==============================================="
echo ""

# 1. Get User Credentials (GitLab Username and Personal Access Token)
echo "Please enter your GitLab Personal Access Token credentials."
echo "These will be stored securely in ~/.netrc (or %USERPROFILE%\\_netrc on Windows)."
echo "Remember to generate a PAT with at least 'read_package_registry' scope."

GITLAB_USERNAME=""
PERSONAL_ACCESS_TOKEN=""

# Loop until a non-empty username is provided
while [ -z "$GITLAB_USERNAME" ]; do
    read -p "Your GitLab Username (e.g., jsmith): " GITLAB_USERNAME
    if [ -z "$GITLAB_USERNAME" ]; then
        echo "Username cannot be empty. Please try again."
    fi
done

while [ -z "$PERSONAL_ACCESS_TOKEN" ]; do
    get_secret_input "Your Personal Access Token string: " PERSONAL_ACCESS_TOKEN
    if [ -z "$PERSONAL_ACCESS_TOKEN" ]; then
        echo "Token cannot be empty. Please try again."
    fi # <--- This was the error. It should be 'fi', not '}'
done

echo "" # New line for better formatting after inputs

# 2. Configure .netrc
NETRC_FILE="$HOME/.netrc"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then # Check for Git Bash / Windows
    NETRC_FILE="$USERPROFILE\\_netrc"
fi

echo "Configuring ${NETRC_FILE}..."

# Check if .netrc exists, if not, create it
if [ ! -f "$NETRC_FILE" ]; then
    touch "$NETRC_FILE"
fi

# Remove existing entry for our GitLab host if it exists
# This uses 'sed -i' for in-place editing. '2>/dev/null || true' suppresses errors if pattern not found.
sed -i "/^machine ${GITLAB_HOST}/,/^$/d" "$NETRC_FILE" 2>/dev/null || true

# Add the new entry with PAT credentials
cat << EOF >> "$NETRC_FILE"

machine ${GITLAB_HOST}
    login ${GITLAB_USERNAME}
    password ${PERSONAL_ACCESS_TOKEN}
EOF

# Set strict permissions for .netrc
if [[ "$OSTYPE" != "msys" && "$OSTYPE" != "win32" ]]; then # Not Windows (Git Bash behaves like Linux for chmod)
    chmod 600 "$NETRC_FILE"
    echo "Permissions for ${NETRC_FILE} set to 600 (owner read/write only)."
else
    echo "Remember to set strict permissions manually for ${NETRC_FILE} on Windows if needed (Security tab in file properties)."
fi

echo ".netrc configured successfully."

# 3. Configure pip.conf
PIP_CONF_DIR="$HOME/.config/pip"
PIP_CONF_FILE="${PIP_CONF_DIR}/pip.conf"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then # Windows
    PIP_CONF_DIR="$APPDATA/pip"
    PIP_CONF_FILE="${PIP_CONF_DIR}/pip.ini"
fi

echo "Configuring ${PIP_CONF_FILE}..."

mkdir -p "$PIP_CONF_DIR"

# Check if pip.conf exists, if not, create it with a basic global section
if [ ! -f "$PIP_CONF_FILE" ]; then
    echo "[global]" > "$PIP_CONF_FILE"
fi

# Remove existing extra-index-url for our private registry if it exists
# This handles both `extra-index-url = ...` and `extra-index-url =`
# Note: This will remove *any* extra-index-url pointing to your GitLab host.
sed -i "/^extra-index-url[[:space:]]*=.*${GITLAB_HOST}/d" "$PIP_CONF_FILE" 2>/dev/null || true

# Add the new extra-index-url pointing to the Group-Level registry
echo "extra-index-url = ${PRIVATE_PYPI_URL}" >> "$PIP_CONF_FILE"


echo "pip.conf configured successfully."

echo ""
echo "Next steps: Remember to activate your virtual environment in new terminal sessions and install the packages !!!"
echo "source ./venv/bin/activate (Linux/macOS)"
echo "./venv/Scripts/activate (Windows PowerShell/CMD)"
echo "pip install -r requirements.txt"