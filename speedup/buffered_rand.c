#include <Python.h>
#include <openssl/err.h>
#include <openssl/rand.h>

#define UNLIKELY(x) __builtin_expect((x), 0)
#define LIKELY(x) __builtin_expect((x), 1)

constexpr size_t BUFFER_SIZE = 256;

static unsigned char buffer[BUFFER_SIZE];
static size_t buffer_pos = BUFFER_SIZE;

static bool
ensure_buffer(size_t needed) {
  if (LIKELY(BUFFER_SIZE - buffer_pos >= needed))
    return true;
  if (UNLIKELY(needed > BUFFER_SIZE)) {
    PyErr_Format(
      PyExc_ValueError, "Requested %zu bytes, but buffer is only %zu bytes", needed,
      BUFFER_SIZE
    );
    return false;
  }

  static_assert(BUFFER_SIZE <= INT_MAX);
  if (UNLIKELY(RAND_bytes(buffer, BUFFER_SIZE) != 1)) {
    PyErr_Format(PyExc_OSError, "OpenSSL RNG error: %lu", ERR_get_error());
    ERR_clear_error();
    return false;
  }

  buffer_pos = 0;
  return true;
}

static size_t
encode_base64url(size_t src_len, const unsigned char src[src_len], char *dst) {
  static const char alphabet[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

  size_t pos = 0;

  // Process 3-byte groups
  for (size_t i = 0; i + 2 < src_len; i += 3) {
    uint_fast32_t val = (src[i] << 16) | (src[i + 1] << 8) | src[i + 2];
    dst[pos++] = alphabet[(val >> 18) & 0x3F];
    dst[pos++] = alphabet[(val >> 12) & 0x3F];
    dst[pos++] = alphabet[(val >> 6) & 0x3F];
    dst[pos++] = alphabet[val & 0x3F];
  }

  // Handle remaining 1 or 2 bytes
  uint_fast8_t remaining = src_len % 3;
  if (remaining == 1) {
    uint_fast32_t val = src[src_len - 1] << 16;
    dst[pos++] = alphabet[(val >> 18) & 0x3F];
    dst[pos++] = alphabet[(val >> 12) & 0x3F];
  } else if (remaining == 2) {
    uint_fast32_t val = (src[src_len - 2] << 16) | (src[src_len - 1] << 8);
    dst[pos++] = alphabet[(val >> 18) & 0x3F];
    dst[pos++] = alphabet[(val >> 12) & 0x3F];
    dst[pos++] = alphabet[(val >> 6) & 0x3F];
  }

  return pos;
}

static PyObject *
buffered_randbytes(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(PyVectorcall_NARGS(nargs) != 1 || !PyLong_CheckExact(args[0]))) {
    PyErr_BadArgument();
    return nullptr;
  }

  size_t n = PyLong_AsSize_t(args[0]);
  if (UNLIKELY((n == (size_t)-1 && PyErr_Occurred()) || !ensure_buffer(n)))
    return nullptr;

  PyObject *result = PyBytes_FromStringAndSize((char *)buffer + buffer_pos, n);
  buffer_pos += n;
  return result;
}

static PyObject *
buffered_rand_urlsafe(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(PyVectorcall_NARGS(nargs) != 1 || !PyLong_CheckExact(args[0]))) {
    PyErr_BadArgument();
    return nullptr;
  }

  size_t n = PyLong_AsSize_t(args[0]);
  if (UNLIKELY((n == (size_t)-1 && PyErr_Occurred()) || !ensure_buffer(n)))
    return nullptr;

  static char encoded[(BUFFER_SIZE * 4 + 2) / 3];
  auto encoded_len = encode_base64url(n, buffer + buffer_pos, encoded);
  buffer_pos += n;
  return PyUnicode_FromStringAndSize(encoded, encoded_len);
}

static PyObject *
buffered_rand_storage_key(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  constexpr size_t RAND_SIZE = 16;
  constexpr Py_ssize_t SUFFIX_MAX_SIZE = 15;

  if (UNLIKELY(
        PyVectorcall_NARGS(nargs) > 1 ||
        (nargs == 1 && !PyUnicode_CheckExact(args[0])) || !ensure_buffer(RAND_SIZE)
      )) {
    PyErr_BadArgument();
    return nullptr;
  }

  Py_ssize_t suffix_len;
  const char *suffix_c;
  if (nargs == 1) {
    suffix_c = PyUnicode_AsUTF8AndSize(args[0], &suffix_len);
    if (UNLIKELY(!suffix_c))
      return nullptr;
    if (UNLIKELY(suffix_len > SUFFIX_MAX_SIZE)) {
      PyErr_SetString(PyExc_ValueError, "Suffix is too long");
      return nullptr;
    }
  } else {
    suffix_len = 0;
    suffix_c = nullptr;
  }

  static char encoded[(RAND_SIZE * 4 + 2) / 3 + SUFFIX_MAX_SIZE];
  auto encoded_len = encode_base64url(RAND_SIZE, buffer + buffer_pos, encoded);
  buffer_pos += RAND_SIZE;

  // Add suffix if provided
  if (suffix_len) {
    memcpy(encoded + encoded_len, suffix_c, suffix_len);
    encoded_len += suffix_len;
  }

  return PyUnicode_FromStringAndSize(encoded, encoded_len);
}

static PyMethodDef methods[] = {
  {
    "buffered_randbytes",
    _PyCFunction_CAST(buffered_randbytes),
    METH_FASTCALL,
    nullptr,
  },
  {
    "buffered_rand_urlsafe",
    _PyCFunction_CAST(buffered_rand_urlsafe),
    METH_FASTCALL,
    nullptr,
  },
  {
    "buffered_rand_storage_key",
    _PyCFunction_CAST(buffered_rand_storage_key),
    METH_FASTCALL,
    nullptr,
  },
  {nullptr, nullptr, 0, nullptr}
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "speedup.buffered_rand",
  nullptr,
  -1,
  methods,
  nullptr,
  nullptr,
  nullptr,
  nullptr
};

PyMODINIT_FUNC
PyInit_buffered_rand(void) {
  return PyModule_Create(&module);
}
