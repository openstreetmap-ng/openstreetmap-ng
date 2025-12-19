use ahash::AHashMap;
use parking_lot::Mutex;
use std::sync::OnceLock;

use pyo3::prelude::*;
use pyo3::types::PyString;

static XML_CACHE: OnceLock<Mutex<AHashMap<String, Py<PyString>>>> = OnceLock::new();

fn xml_cache() -> &'static Mutex<AHashMap<String, Py<PyString>>> {
    XML_CACHE.get_or_init(|| Mutex::new(AHashMap::new()))
}

#[pyfunction(signature = (name, /, xml = None))]
fn xattr_json(name: Py<PyString>, xml: Option<&str>) -> Py<PyString> {
    let _xml = xml;
    name
}

#[pyfunction(signature = (name, /, xml = None))]
fn xattr_xml(py: Python<'_>, name: &str, xml: Option<&str>) -> PyResult<Py<PyString>> {
    let source = xml.unwrap_or(name);
    let mut cache = xml_cache().lock();

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
