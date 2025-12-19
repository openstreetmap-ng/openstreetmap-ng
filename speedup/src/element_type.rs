use std::hint::unlikely;

use pyo3::exceptions::{PyNotImplementedError, PyOverflowError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDict, PyList, PyString, PyTuple};

const NODE_TYPE_NUM: u64 = 0;
const WAY_TYPE_NUM: u64 = 1;
const RELATION_TYPE_NUM: u64 = 2;

const TYPE_SHIFT: u8 = 60;
const TYPE_MASK: u64 = 0b11;
const SIGN_MASK: u64 = 1 << 59;
const ID_MASK: u64 = (1 << 56) - 1;

static NODE_STR: PyOnceLock<Py<PyString>> = PyOnceLock::new();
static WAY_STR: PyOnceLock<Py<PyString>> = PyOnceLock::new();
static RELATION_STR: PyOnceLock<Py<PyString>> = PyOnceLock::new();

fn type_num_from_typed_id(typed_id: u64) -> u64 {
    (typed_id >> TYPE_SHIFT) & TYPE_MASK
}

fn element_id_from_typed_id(typed_id: u64) -> i64 {
    let mut element_id = (typed_id & ID_MASK) as i64;
    if (typed_id & SIGN_MASK) != 0 {
        element_id = -element_id;
    }
    element_id
}

fn type_str_from_num(py: Python<'_>, type_num: u64) -> PyResult<Py<PyString>> {
    let out = match type_num {
        NODE_TYPE_NUM => NODE_STR.get_or_init(py, || PyString::new(py, "node").unbind()),
        WAY_TYPE_NUM => WAY_STR.get_or_init(py, || PyString::new(py, "way").unbind()),
        RELATION_TYPE_NUM => {
            RELATION_STR.get_or_init(py, || PyString::new(py, "relation").unbind())
        }
        _ => return Err(PyNotImplementedError::new_err("Unsupported element type")),
    };
    Ok(out.clone_ref(py))
}

fn type_num_from_str(type_: &str) -> PyResult<u64> {
    match type_ {
        "node" => Ok(NODE_TYPE_NUM),
        "way" => Ok(WAY_TYPE_NUM),
        "relation" => Ok(RELATION_TYPE_NUM),
        "" => Err(PyValueError::new_err("Element type is empty")),
        _ => Err(PyNotImplementedError::new_err(format!(
            "Unsupported element type {:?}",
            type_
        ))),
    }
}

fn typed_element_id_impl(type_num: u64, id: i64) -> PyResult<u64> {
    let abs = id.unsigned_abs();
    if unlikely(abs > ID_MASK) {
        let msg = if id < 0 {
            format!("ElementId {id} is too small for TypedElementId")
        } else {
            format!("ElementId {id} is too large for TypedElementId")
        };
        return Err(PyOverflowError::new_err(msg));
    }

    let result = if id < 0 { abs | SIGN_MASK } else { abs };
    Ok(result | (type_num << TYPE_SHIFT))
}

#[pyfunction]
fn element_id(typed_id: u64) -> i64 {
    element_id_from_typed_id(typed_id)
}

#[pyfunction]
fn element_type(py: Python<'_>, typed_id: u64) -> PyResult<Py<PyString>> {
    type_str_from_num(py, type_num_from_typed_id(typed_id))
}

#[pyfunction]
fn typed_element_id(type_: &str, id: i64) -> PyResult<u64> {
    typed_element_id_impl(type_num_from_str(type_)?, id)
}

#[pyfunction]
fn versioned_typed_element_id(type_: &str, s: &str) -> PyResult<(u64, i64)> {
    let s = s.trim();
    if unlikely(s.is_empty()) {
        return Err(PyValueError::new_err(format!(
            "Element reference {:?} is invalid",
            s
        )));
    }

    let (id_s, version_s) = s
        .split_once('v')
        .ok_or_else(|| PyValueError::new_err(format!("Element reference {:?} is invalid", s)))?;

    let id = id_s
        .parse()
        .map_err(|_| PyValueError::new_err(format!("Element reference {:?} is invalid", s)))?;
    if unlikely(id == 0) {
        return Err(PyValueError::new_err("Element id must be non-zero"));
    }

    let version = version_s
        .parse()
        .map_err(|_| PyValueError::new_err(format!("Element reference {:?} is invalid", s)))?;
    if unlikely(version <= 0) {
        return Err(PyValueError::new_err("Element version must be positive"));
    }

    Ok((
        typed_element_id_impl(type_num_from_str(type_)?, id)?,
        version,
    ))
}

#[pyfunction]
fn split_typed_element_id(py: Python<'_>, id: i64) -> PyResult<(Py<PyString>, i64)> {
    let typed_id = id as u64;
    let element_id = element_id_from_typed_id(typed_id);
    let type_num = type_num_from_typed_id(typed_id);
    let type_str = type_str_from_num(py, type_num)?;
    Ok((type_str, element_id))
}

#[pyfunction]
fn split_typed_element_ids(py: Python<'_>, ids: &Bound<'_, PyList>) -> PyResult<Py<PyList>> {
    let out = PyList::empty(py);

    ids.iter().try_for_each(|item| {
        let typed_id = if let Ok(v) = item.extract::<i64>() {
            v
        } else if let Ok(dict) = item.cast::<PyDict>() {
            dict.get_item("typed_id")?
                .ok_or_else(|| PyValueError::new_err("Missing 'typed_id'"))?
                .extract()?
        } else {
            return Err(PyValueError::new_err(
                "Expected int or dict with 'typed_id'",
            ));
        };

        let (type_str, element_id) = split_typed_element_id(py, typed_id)?;
        let element_id_obj = element_id.into_pyobject(py)?.into_any().unbind();
        let tuple = PyTuple::new(py, [type_str.into_any(), element_id_obj])?;
        out.append(tuple)?;
        Ok(())
    })?;

    Ok(out.unbind())
}

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(element_id, m)?)?;
    m.add_function(wrap_pyfunction!(element_type, m)?)?;
    m.add_function(wrap_pyfunction!(typed_element_id, m)?)?;
    m.add_function(wrap_pyfunction!(versioned_typed_element_id, m)?)?;
    m.add_function(wrap_pyfunction!(split_typed_element_id, m)?)?;
    m.add_function(wrap_pyfunction!(split_typed_element_ids, m)?)?;
    Ok(())
}
