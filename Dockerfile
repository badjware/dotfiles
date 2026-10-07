FROM archlinux:latest

RUN pacman -Syu --noconfirm --needed base-devel git chezmoi sudo zsh && \
    rm -rf /var/cache/pacman/pkg/*

RUN useradd --create-home --uid 1000 --shell /bin/zsh user && \
    echo 'user ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/user && \
    mkdir -p /data && \
    chown user:user /data

USER user
WORKDIR /home/user
ENV PATH="/home/user/.local/bin:$PATH"
ENV SHELL="/bin/zsh"

COPY --chown=user:user . /home/user/.local/share/chezmoi
RUN --mount=type=secret,id=npmrc,target=/etc/npmrc,mode=0444 \
    CHEZMOI_CHASSIS_TYPE=container chezmoi init --apply && \
    sudo rm -rf /var/cache/pacman/pkg/* && \
    rm -rf ~/.cache/chezmoi ~/.cache/go-build ~/.cache/pikaur ~/.cache/pip


ENV CPTR_DATA_DIR="/data"
EXPOSE 8000
VOLUME ["/data"]

ENTRYPOINT ["cptr"]
CMD ["run", "--host", "0.0.0.0", "--port", "8000", "--headless"]
