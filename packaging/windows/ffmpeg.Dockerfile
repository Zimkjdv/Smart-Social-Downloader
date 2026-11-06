# Native Windows FFmpeg without external codec libraries. Sources ship with it.
FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
COPY debian.sources /etc/apt/sources.list.d/ssdl.sources
RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends make gcc libc6-dev gcc-mingw-w64-x86-64-posix pkg-config xz-utils \
    && rm -rf /var/lib/apt/lists/*
COPY ffmpeg-8.1.3.tar.xz /build/source.tar.xz
COPY zlib-1.3.2.tar.xz /build/zlib-source.tar.xz
WORKDIR /build
RUN tar xf zlib-source.tar.xz && cd zlib-1.3.2 \
    && make -f win32/Makefile.gcc PREFIX=x86_64-w64-mingw32- -j4 libz.a \
    && cp libz.a /usr/x86_64-w64-mingw32/lib/ \
    && cp zlib.h zconf.h /usr/x86_64-w64-mingw32/include/
RUN tar xf source.tar.xz && cd ffmpeg-8.1.3 \
    && ./configure --enable-cross-compile --target-os=mingw32 --arch=x86_64 \
       --cross-prefix=x86_64-w64-mingw32- --disable-autodetect --disable-gpl --disable-nonfree \
       --disable-version3 --disable-x86asm --disable-debug --disable-doc --disable-ffplay \
       --disable-ffprobe --disable-avdevice --disable-hwaccels --disable-shared --enable-static \
       --disable-encoders --enable-encoder=png,mjpeg --enable-w32threads --enable-zlib --enable-schannel \
       --extra-ldflags=-static \
    && make -j4 ffmpeg.exe \
    && mkdir -p /out/licenses /out/sources \
    && cp ffmpeg.exe /out/ffmpeg.exe \
    && cp COPYING.LGPLv2.1 /out/licenses/FFmpeg-LGPL-2.1.txt \
    && cp /usr/share/doc/mingw-w64-common/copyright /out/licenses/MinGW-w64.txt \
    && cp /usr/share/doc/gcc-mingw-w64-base/copyright /out/licenses/GCC-runtime.txt \
    && cp /build/source.tar.xz /out/sources/ffmpeg-8.1.3.tar.xz \
    && cp ffbuild/config.log /out/sources/ffmpeg-config.log \
    && cp /build/zlib-source.tar.xz /out/sources/zlib-1.3.2.tar.xz \
    && cp /build/zlib-1.3.2/LICENSE /out/licenses/Zlib.txt
FROM scratch
COPY --from=build /out/ /
