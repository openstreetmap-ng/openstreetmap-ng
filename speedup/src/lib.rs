#![feature(likely_unlikely)]

mod buffered_rand;
mod element_type;
mod gps_batches;
mod xattr;
mod xml_parse;
mod xml_unparse;

use pyo3::prelude::*;

#[pyclass]
struct GPSTracePixelBatches {
    inner: gps_batches::PixelBatches,
}

#[pymethods]
impl GPSTracePixelBatches {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(&mut self) -> Option<Vec<(u32, u32)>> {
        self.inner.next()
    }
}

#[pyfunction]
fn gps_trace_pixel_batches(
    segments: Vec<Vec<(f64, f64)>>,
    zoom: u8,
) -> PyResult<GPSTracePixelBatches> {
    gps_batches::PixelBatches::new(segments, zoom)
        .map(|inner| GPSTracePixelBatches { inner })
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Invalid GPS coordinates or zoom"))
}

#[pymodule]
fn speedup(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(gps_trace_pixel_batches, m)?)?;
    buffered_rand::register(m)?;
    element_type::register(m)?;
    xattr::register(m)?;
    xml_parse::register(m)?;
    xml_unparse::register(m)?;
    Ok(())
}
