use ahash::AHashMap;
use parking_lot::Mutex;

use pyo3::prelude::*;
use pyo3::sync::{MutexExt, PyOnceLock};
use pyo3::types::PyString;

static XML_CACHE: PyOnceLock<Mutex<AHashMap<String, Py<PyString>>>> = PyOnceLock::new();

#[pyfunction(signature = (name, /, xml = None))]
fn xattr_json(name: Py<PyString>, xml: Option<&str>) -> Py<PyString> {
    let _xml = xml;
    name
}

#[pyfunction(signature = (name, /, xml = None))]
fn xattr_xml(py: Python<'_>, name: &str, xml: Option<&str>) -> PyResult<Py<PyString>> {
    let source = xml.unwrap_or(name);
    let mut cache = XML_CACHE
        .get_or_init(py, || Mutex::new(AHashMap::new()))
        .lock_py_attached(py);

    if let Some(cached) = cache.get(source) {
        return Ok(cached.clone_ref(py));
    }

    let value = PyString::new(py, &format!("@{source}")).unbind();
    cache.insert(source.to_owned(), value.clone_ref(py));
    Ok(value)
}

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(xattr_json, m)?)?;
    m.add_function(wrap_pyfunction!(xattr_xml, m)?)?;
    Ok(())
}
