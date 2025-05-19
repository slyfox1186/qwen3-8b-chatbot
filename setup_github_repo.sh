#!/bin/bash

# Setup script for creating a new GitHub repository for the Qwen3-8B Chatbot project

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up GitHub repository for Qwen3-8B Chatbot...${NC}"

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}Git is not installed. Please install git and try again.${NC}"
    exit 1
fi

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${YELLOW}GitHub CLI is not installed. We'll use git commands only.${NC}"
    USE_GH_CLI=false
else
    USE_GH_CLI=true
    # Check if logged in to GitHub CLI
    if ! gh auth status &> /dev/null; then
        echo -e "${YELLOW}Please log in to GitHub CLI:${NC}"
        gh auth login
    fi
fi

# Initialize git repository if not already initialized
if [ ! -d .git ]; then
    echo -e "${GREEN}Initializing git repository...${NC}"
    git init
fi

# Add all files
echo -e "${GREEN}Adding files to git...${NC}"
git add .

# Commit changes
echo -e "${GREEN}Committing files...${NC}"
git commit -m "Initial commit: Qwen3-8B Chatbot with token streaming"

# Create GitHub repository
REPO_NAME="qwen3-8b-chatbot"
REPO_DESCRIPTION="A full-stack chatbot application using Qwen3-8B with token streaming"

if [ "$USE_GH_CLI" = true ]; then
    echo -e "${GREEN}Creating GitHub repository using GitHub CLI...${NC}"
    gh repo create "$REPO_NAME" --public --description "$REPO_DESCRIPTION" --source=. --push
else
    echo -e "${GREEN}Please create a new repository on GitHub named '$REPO_NAME'${NC}"
    echo -e "${YELLOW}Visit: https://github.com/new${NC}"
    echo -e "${YELLOW}Repository name: $REPO_NAME${NC}"
    echo -e "${YELLOW}Description: $REPO_DESCRIPTION${NC}"
    echo -e "${YELLOW}Make it Public${NC}"
    echo -e "${YELLOW}Do NOT initialize with README, .gitignore, or license${NC}"
    
    read -p "Press Enter after you've created the repository..."
    
    echo -e "${GREEN}Adding remote origin...${NC}"
    git remote add origin "https://github.com/slyfox1186/$REPO_NAME.git"
    
    echo -e "${GREEN}Pushing to GitHub...${NC}"
    git push -u origin main || git push -u origin master
fi

echo -e "${GREEN}Repository setup complete!${NC}"
echo -e "${GREEN}Your repository is now available at: https://github.com/slyfox1186/$REPO_NAME${NC}"
echo -e "${YELLOW}Don't forget to update the placeholder image URL in REDDIT-README.md after you add a demo screenshot.${NC}"
