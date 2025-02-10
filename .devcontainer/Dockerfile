FROM mcr.microsoft.com/vscode/devcontainers/python:3.13

ENV POETRY_VERSION="1.7.1"

ARG USERNAME=vscode

# Get vscode to work with sudo on all commands with no required password.
RUN apt-get install -y sudo \
    && echo $USERNAME ALL=\(ALL\) NOPASSWD: ALL > /etc/sudoers.d/$USERNAME \
    # && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

RUN apt-get update \
    && apt-get -y install --no-install-recommends apt-utils 2>&1 \
    && apt-get -y install \
    curl \
    emacs \
    exa \
    fd-find \
    fzf \
    git \
    iputils-ping \
    iproute2 \
    less \
    libsodium-dev \
    lsb-release \
    man-db \
    manpages \
    net-tools \
    nodejs \
    npm \
    openssh-client \
    procps \
    sudo \
    tldr \
    unzip \
    vim \
    libgtk2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libnotify-dev \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    libxtst6 \
    xauth \
    xvfb \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

COPY --chown=vscode:vscode .devcontainer/scripts/notify-dev-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/notify-dev-entrypoint.sh

COPY --chown=vscode:vscode .devcontainer/scripts/installations.sh /usr/local/bin/
RUN chmod -R 765 /usr/local/bin/installations.sh

# Set the default user, which is remoteUser as defined in the devcontainer.json file.
USER $USERNAME

EXPOSE 6012
