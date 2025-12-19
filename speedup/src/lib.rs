#![feature(likely_unlikely)]

mod buffered_rand;
mod element_type;
mod xattr;
mod xml_parse;
mod xml_unparse;

use pyo3::prelude::*;

#[pymodule]
fn speedup(m: &Bound<'_, PyModule>) -> PyResult<()> {
    buffered_rand::register(m)?;
    element_type::register(m)?;
    xattr::register(m)?;
    xml_parse::register(m)?;
    xml_unparse::register(m)?;
    Ok(())
}
