#!/bin/bash
if [ -z "$1" ]; then
  echo "Usage: ./release.sh <version>"
  echo "Example: ./release.sh 1.1.0"
  exit 1
fi

VERSION=$1

echo "Tagging release v$VERSION and pushing to trigger GitHub Actions..."
git tag -a "v$VERSION" -m "Release v$VERSION"
git push github "v$VERSION"
git push gitlab "v$VERSION"

echo ""
echo "🚀 Done! GitHub Actions will now automatically test, package, and publish the plugin."
