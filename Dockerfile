FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates clang lld llvm make gcc bc bison flex cpio dwarves libssl-dev libelf-dev python3 xz-utils && rm -rf /var/lib/apt/lists/*
