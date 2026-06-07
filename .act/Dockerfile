# Custom act runner image: catthehacker's medium runner + gh CLI.
#
# Real GitHub-hosted runners ship `gh` pre-installed, but the ~1.5GB
# `catthehacker/ubuntu:act-latest` does not. Workflows in this repo invoke
# gh (PR creation, issue comments, label management), so we bake it in once
# instead of paying the apt-install cost on every local act run.
#
# Build: make act-build
# Used by: .actrc (-P ubuntu-latest=act-runner-with-gh:latest)

FROM catthehacker/ubuntu:act-latest

RUN type -p curl >/dev/null || (apt-get update && apt-get install -y curl) \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
 && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/* \
 && gh --version
