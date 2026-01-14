# AI4Infra Nginx WAF Image (Fixed & Optimized)
FROM openresty/openresty:1.27.1.1-alpine-fat AS builder

# 1. Build Dependencies (Fixed)
# Added pcre-dev, curl-dev for ModSecurity build
RUN apk add --no-cache \
    git gcc g++ make linux-headers curl perl \
    pcre-dev pcre2-dev openssl-dev zlib-dev curl-dev \
    automake autoconf libtool pkgconf \
    libxml2-dev yajl-dev lmdb-dev libmaxminddb-dev

WORKDIR /opt

# 2. ModSecurity v3 (Release Tarball)
# - Using Tarball to avoid git clone hangs
# - Disabled curl/geoip to avoid OpenSSL library conflicts (symbol not found)
RUN curl -fSL https://github.com/SpiderLabs/ModSecurity/releases/download/v3.0.12/modsecurity-v3.0.12.tar.gz -o modsecurity.tar.gz && \
    tar xzf modsecurity.tar.gz && \
    cd modsecurity-v3.0.12 && \
    ./build.sh && \
    ./configure --without-curl --without-geoip && \
    make && make install

# 3. Nginx Connector (Tarball + Full Build)
# - Using Tarball for reliability
# - Using 'make' (full build) because 'make modules' target is missing in OpenResty root
ARG RESTY_VERSION=1.27.1.1
WORKDIR /opt
RUN curl -fSL https://github.com/SpiderLabs/ModSecurity-nginx/archive/refs/heads/master.tar.gz -o modsec-nginx.tar.gz && \
    tar xzf modsec-nginx.tar.gz && \
    mv ModSecurity-nginx-master ModSecurity-nginx && \
    curl -fSL https://openresty.org/download/openresty-${RESTY_VERSION}.tar.gz -o openresty.tar.gz && \
    tar xzf openresty.tar.gz && \
    cd openresty-${RESTY_VERSION} && \
    ./configure --with-compat --add-dynamic-module=../ModSecurity-nginx && \
    make -j2

# 4. Final Image Assembly
FROM openresty/openresty:1.27.1.1-alpine-fat

# Runtime Dependencies (Fixed)
# Added pcre for libmodsecurity runtime dependency
RUN apk add --no-cache \
    libstdc++ libmaxminddb libxml2 yajl lmdb \
    bash curl perl pcre

# Install OIDC
RUN opm get zmartzone/lua-resty-openidc

# Copy Artifacts
COPY --from=builder /usr/local/modsecurity /usr/local/modsecurity
COPY --from=builder /usr/local/lib/libmodsecurity.so* /usr/local/lib/
# Using wildcard path to handle build directory variance
COPY --from=builder /opt/openresty-*/build/nginx-*/objs/ngx_http_modsecurity_module.so /usr/local/openresty/nginx/modules/

# OWASP CRS (v3.3.5 Stable)
# Added cp crs-setup.conf to avoid config error
RUN curl -fSL https://github.com/coreruleset/coreruleset/archive/v3.3.5.tar.gz -o crs.tar.gz && \
    tar xzf crs.tar.gz && \
    mv coreruleset-3.3.5 /usr/local/owasp-crs && \
    rm crs.tar.gz && \
    cp /usr/local/owasp-crs/crs-setup.conf.example /usr/local/owasp-crs/crs-setup.conf

EXPOSE 80 443
CMD ["/usr/local/openresty/bin/openresty", "-g", "daemon off;"]
