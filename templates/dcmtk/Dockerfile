FROM debian:bookworm-slim

LABEL maintainer="AI4Infra Team"
LABEL description="DCMTK Tools Container for DICOM Operations"

# Install DCMTK
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    dcmtk \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /workspace /examples

WORKDIR /workspace

# Default command: keep container alive
CMD ["tail", "-f", "/dev/null"]
