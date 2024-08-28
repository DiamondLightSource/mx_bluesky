FROM python:3.11 AS build

RUN pip install setuptools_scm

# Copy the pyproject.toml and install dependencies for better caching when developing
# & rerunning deployment scripts
COPY pyproject.toml /app/hyperion/
WORKDIR "/app/hyperion"
RUN mkdir -p src/mx_bluesky

# This enables us to cache the pip install without needing _version.py
# see https://setuptools-scm.readthedocs.io/en/latest/usage/
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_MX_BLUESKY=1.0.0 pip install \
    --no-cache-dir --no-compile -e .

# Check out and install dodal locally with no dependencies as this may be a different version to what
# is referred to in the setup.cfg, but we don't care as it will be overridden by bind mounts in the
# running container
RUN mkdir ../dodal && \
git clone https://github.com/DiamondLightSource/dodal.git ../dodal && \
pip install --no-cache-dir --no-compile --no-deps -e ../dodal

#
# Everything above this line should be in the image cache unless pyproject.toml changes
#
ADD .git /app/hyperion/.git
RUN git restore .

# Regenerate _version.py with the correct version - this should run quickly since we already have our dependencies
RUN rm src/mx_bluesky/_version.py
RUN pip install --no-cache-dir --no-compile -e .

ENTRYPOINT /app/hyperion/utility_scripts/docker/entrypoint.sh

EXPOSE 5005
