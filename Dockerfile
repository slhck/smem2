# Base stage with common dependencies
FROM python:3.13-slim AS base

WORKDIR /app

# Copy the entire project
COPY . .

# Install the project and its dependencies
RUN pip3 install .

# Test stage for running tests
FROM base AS test

# Install pytest for testing
RUN pip3 install pytest

# Set the entrypoint to run tests
ENTRYPOINT [ "pytest" ]

# Production stage for running smem2 (default)
FROM base AS production

# Set the entrypoint to execute the smem2 module
ENTRYPOINT [ "python3", "-m", "smem2" ]
