#include <Python.h>
#include <methodobject.h>
#include <stdint.h>
#include <stdlib.h>

#define UNLIKELY(x) __builtin_expect((x), 0)
#define LIKELY(x) __builtin_expect((x), 1)
#define PyScoped PyObject *__attribute__((cleanup(Py_XDECREFP)))

constexpr uint64_t NODE_TYPE_NUM = 0;
constexpr uint64_t WAY_TYPE_NUM = 1;
constexpr uint64_t RELATION_TYPE_NUM = 2;
constexpr uint64_t SIGN_MASK = 1ULL << 59;

#pragma region Globals

static PyObject *node_str;
static PyObject *way_str;
static PyObject *relation_str;
static PyObject *typed_id_key;

#pragma endregion
#pragma region Cleanup

static inline void
Py_XDECREFP(PyObject **ptr) {
  Py_XDECREF(*ptr);
}

#pragma endregion

static PyObject *
element_type(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(PyVectorcall_NARGS(nargs) != 1 || !PyUnicode_CheckExact(args[0]))) {
    PyErr_BadArgument();
    return nullptr;
  }

  const char *str = PyUnicode_AsUTF8(args[0]);
  switch (str[0]) {
  case 'n':
    return node_str;
  case 'w':
    return way_str;
  case 'r':
    return relation_str;
  case '\0':
    PyErr_SetString(PyExc_ValueError, "Element type is empty");
    return nullptr;
  default:
    PyErr_Format(PyExc_ValueError, "Unknown element type '%s'", str);
    return nullptr;
  }
}

// Encode element type and id into a 64-bit integer:
// [ 2 reserved bits ][ 2 type bits ][ 1 sign bit ][ 3 reserved bits ][ 56 id bits ]
static PyObject *
typed_element_id_impl(PyObject *type, int64_t id) {
  uint64_t result;

  if (id < 0) {
    if (UNLIKELY(id <= -(1LL << 56))) {
      PyErr_Format(
        PyExc_OverflowError, "ElementId %lld is too small for TypedElementId", id
      );
      return nullptr;
    }
    result = -id | SIGN_MASK;
  } else {
    if (UNLIKELY(id >= (1LL << 56))) {
      PyErr_Format(
        PyExc_OverflowError, "ElementId %lld is too large for TypedElementId", id
      );
      return nullptr;
    }
    result = id;
  }

  // Fast-path for interned strings
  if (type == node_str)
    return PyLong_FromUnsignedLongLong(result | (NODE_TYPE_NUM << 60));
  if (type == way_str)
    return PyLong_FromUnsignedLongLong(result | (WAY_TYPE_NUM << 60));
  if (type == relation_str)
    return PyLong_FromUnsignedLongLong(result | (RELATION_TYPE_NUM << 60));

  const char *str = PyUnicode_AsUTF8(type);
  switch (str[0]) {
  case 'n':
    return PyLong_FromUnsignedLongLong(result | (NODE_TYPE_NUM << 60));
  case 'w':
    return PyLong_FromUnsignedLongLong(result | (WAY_TYPE_NUM << 60));
  case 'r':
    return PyLong_FromUnsignedLongLong(result | (RELATION_TYPE_NUM << 60));
  default:
    PyErr_Format(PyExc_NotImplementedError, "Unsupported element type '%s'", str);
    return nullptr;
  }
}

static PyObject *
typed_element_id(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(
        PyVectorcall_NARGS(nargs) != 2 || !PyUnicode_CheckExact(args[0]) ||
        !PyLong_CheckExact(args[1])
      )) {
    PyErr_BadArgument();
    return nullptr;
  }

  int overflow;
  auto id = PyLong_AsLongLongAndOverflow(args[1], &overflow);
  if (UNLIKELY(overflow))
    id = overflow == 1 ? LLONG_MAX : LLONG_MIN;

  return typed_element_id_impl(args[0], id);
}

static PyObject *
versioned_typed_element_id(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(
        PyVectorcall_NARGS(nargs) != 2 || !PyUnicode_CheckExact(args[0]) ||
        !PyUnicode_CheckExact(args[1])
      )) {
    PyErr_BadArgument();
    return nullptr;
  }

  Py_ssize_t size;
  const char *str = PyUnicode_AsUTF8AndSize(args[1], &size);
  if (UNLIKELY(!size || size > (20 * 2) + 2))
    goto invalid;

  errno = 0;
  char *end_ptr;
  auto id = strtoll(str, &end_ptr, 10);
  if (UNLIKELY(end_ptr == str || *end_ptr != 'v' || errno != 0))
    goto invalid;
  if (UNLIKELY(!id)) {
    PyErr_Format(PyExc_ValueError, "Element id must be non-zero");
    return nullptr;
  }

  errno = 0;
  auto version = strtoll(end_ptr + 1, &end_ptr, 10);
  if (UNLIKELY(end_ptr == str || *end_ptr != '\0' || errno != 0))
    goto invalid;
  if (UNLIKELY(version <= 0)) {
    PyErr_Format(PyExc_ValueError, "Element version must be positive");
    return nullptr;
  }

  {
    PyScoped typed_id = typed_element_id_impl(args[0], id);
    PyScoped version_py = PyLong_FromLongLong(version);
    return PyTuple_Pack(2, typed_id, version_py);
  }

invalid:
  PyErr_Format(PyExc_ValueError, "Element reference '%U' is invalid", args[1]);
  return nullptr;
}

static PyObject *
split_typed_element_id_impl(PyObject *id_obj) {
  int overflow;
  auto id = (uint64_t)PyLong_AsLongLongAndOverflow(id_obj, &overflow);
  if (UNLIKELY(overflow))
    id = (uint64_t)(overflow == 1 ? LLONG_MAX : LLONG_MIN);

  auto element_id = (int64_t)(id & ((1ULL << 56) - 1));
  if (id & SIGN_MASK)
    element_id = -element_id;

  PyScoped element_id_py = PyLong_FromLongLong(element_id);
  if (UNLIKELY(!element_id_py))
    return nullptr;

  auto type_num = (id >> 60) & 0b11;
  switch (type_num) {
  case NODE_TYPE_NUM:
    return PyTuple_Pack(2, node_str, element_id_py);
  case WAY_TYPE_NUM:
    return PyTuple_Pack(2, way_str, element_id_py);
  case RELATION_TYPE_NUM:
    return PyTuple_Pack(2, relation_str, element_id_py);
  default:
    PyErr_Format(
      PyExc_NotImplementedError, "Unsupported element type number %llu in %S", type_num,
      id_obj
    );
    return nullptr;
  }
}

static PyObject *
split_typed_element_id(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(PyVectorcall_NARGS(nargs) != 1 || !PyLong_CheckExact(args[0]))) {
    PyErr_BadArgument();
    return nullptr;
  }
  return split_typed_element_id_impl(args[0]);
}

static PyObject *
split_typed_element_ids(const PyObject *, PyObject *const *args, Py_ssize_t nargs) {
  if (UNLIKELY(PyVectorcall_NARGS(nargs) != 1 || !PyList_CheckExact(args[0]))) {
    PyErr_BadArgument();
    return nullptr;
  }

  auto size = PyList_GET_SIZE(args[0]);
  PyObject *result = PyList_New(size);
  if (UNLIKELY(!result))
    return nullptr;

  for (typeof(size) i = 0; i < size; i++) {
    PyObject *item = PyList_GET_ITEM(args[0], i);

    if (!PyLong_CheckExact(item)) {
      item = PyDict_GetItem(item, typed_id_key);
      if (UNLIKELY(!item || !PyLong_CheckExact(item))) {
        Py_DECREF(result);
        PyErr_BadArgument();
        return nullptr;
      }
    }

    PyObject *tuple = split_typed_element_id_impl(item);
    if (UNLIKELY(!tuple)) {
      Py_DECREF(result);
      return nullptr;
    }

    PyList_SET_ITEM(result, i, tuple);
  }

  return result;
}

static PyMethodDef methods[] = {
  {
    "element_type",
    _PyCFunction_CAST(element_type),
    METH_FASTCALL,
    nullptr,
  },
  {
    "typed_element_id",
    _PyCFunction_CAST(typed_element_id),
    METH_FASTCALL,
    nullptr,
  },
  {
    "versioned_typed_element_id",
    _PyCFunction_CAST(versioned_typed_element_id),
    METH_FASTCALL,
    nullptr,
  },
  {
    "split_typed_element_id",
    _PyCFunction_CAST(split_typed_element_id),
    METH_FASTCALL,
    nullptr,
  },
  {
    "split_typed_element_ids",
    _PyCFunction_CAST(split_typed_element_ids),
    METH_FASTCALL,
    nullptr,
  },
  {nullptr, nullptr, 0, nullptr}
};

// Module definition
static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "speedup.element_type",
  nullptr,
  -1,
  methods,
  nullptr,
  nullptr,
  nullptr,
  nullptr
};

PyMODINIT_FUNC
PyInit_element_type(void) {
  node_str = PyUnicode_InternFromString("node");
  way_str = PyUnicode_InternFromString("way");
  relation_str = PyUnicode_InternFromString("relation");
  typed_id_key = PyUnicode_InternFromString("typed_id");

  return PyModule_Create(&module);
}
