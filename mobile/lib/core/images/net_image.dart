import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../net/api_client.dart';

/// Product pictures: fetched through the pinned client (never a second,
/// unpinned HTTP stack), kept on disk in the app's private cache (≤150 MB,
/// oldest out first), decoded at the size they are shown.
class ImageStore {
  ImageStore(this._api, String cacheDir) : _dir = Directory('$cacheDir/img');

  final ApiClient _api;
  final Directory _dir;
  final Map<String, Future<Uint8List?>> _inflight = {};
  int _writes = 0;
  static const _maxBytes = 150 * 1024 * 1024;

  Future<Uint8List?> load(String url) =>
      _inflight[url] ??= _load(url).whenComplete(() => _inflight.remove(url));

  Future<Uint8List?> _load(String url) async {
    final file = File('${_dir.path}/${_fileName(url)}');
    try {
      return await file.readAsBytes();
    } on FileSystemException {
      // not cached yet: fetch it
    }
    final bytes = await _api.fetchImage(url);
    if (bytes != null) {
      try {
        await _dir.create(recursive: true);
        await file.writeAsBytes(bytes, flush: false);
        if (++_writes % 40 == 0) unawaited(_trim());
      } on FileSystemException {
        // a full disk only costs the cache
      }
    }
    return bytes;
  }

  Future<void> _trim() async {
    try {
      final files = await _dir.list().where((e) => e is File).cast<File>().toList();
      final stats = <(File, FileStat)>[for (final f in files) (f, f.statSync())];
      var total = stats.fold<int>(0, (sum, s) => sum + s.$2.size);
      if (total <= _maxBytes) return;
      stats.sort((a, b) => a.$2.modified.compareTo(b.$2.modified));
      for (final (file, stat) in stats) {
        if (total <= _maxBytes * 0.8) break;
        await file.delete();
        total -= stat.size;
      }
    } on FileSystemException {
      // best effort
    }
  }

  /// 64-bit FNV-1a of the URL — a file name, not a security boundary.
  static String _fileName(String url) {
    var hash = 0xcbf29ce484222325;
    for (final unit in url.codeUnits) {
      hash ^= unit;
      hash = (hash * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF;
    }
    return hash.toUnsigned(64).toRadixString(16);
  }
}

@immutable
class StoreImage extends ImageProvider<StoreImage> {
  const StoreImage(this.url, this.store);

  final String url;
  final ImageStore store;

  @override
  Future<StoreImage> obtainKey(ImageConfiguration configuration) => SynchronousFuture(this);

  @override
  ImageStreamCompleter loadImage(StoreImage key, ImageDecoderCallback decode) =>
      MultiFrameImageStreamCompleter(codec: _codec(decode), scale: 1.0, debugLabel: url);

  Future<ui.Codec> _codec(ImageDecoderCallback decode) async {
    final bytes = await store.load(url);
    if (bytes == null || bytes.isEmpty) throw StateError('image unavailable');
    return decode(await ui.ImmutableBuffer.fromUint8List(bytes));
  }

  @override
  bool operator ==(Object other) => other is StoreImage && other.url == url;

  @override
  int get hashCode => url.hashCode;
}
