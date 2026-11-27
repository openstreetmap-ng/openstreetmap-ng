use std::collections::BTreeSet;

const BATCH_STEPS: usize = 8192;
const MAX_LATITUDE: f64 = 85.0511287798066;

struct Line {
    x: i64,
    y: i64,
    end_x: i64,
    end_y: i64,
    dx: i64,
    dy: i64,
    sx: i64,
    sy: i64,
    error: i64,
    done: bool,
}

impl Line {
    fn new(a: (i64, i64), b: (i64, i64), width: i64) -> Self {
        let (mut end_x, end_y) = b;
        if end_x - a.0 > width / 2 {
            end_x -= width;
        }
        if a.0 - end_x > width / 2 {
            end_x += width;
        }
        let ((x, y), (end_x, end_y)) = if a <= (end_x, end_y) {
            (a, (end_x, end_y))
        } else {
            ((end_x, end_y), a)
        };
        let dx = (end_x - x).abs();
        let dy = -(end_y - y).abs();
        Self {
            x,
            y,
            end_x,
            end_y,
            dx,
            dy,
            sx: if x < end_x { 1 } else { -1 },
            sy: if y < end_y { 1 } else { -1 },
            error: dx + dy,
            done: false,
        }
    }

    fn next(&mut self) -> Option<(i64, i64)> {
        if self.done {
            return None;
        }
        let result = (self.x, self.y);
        if self.x == self.end_x && self.y == self.end_y {
            self.done = true;
        } else {
            let twice = 2 * self.error;
            if twice >= self.dy {
                self.error += self.dy;
                self.x += self.sx;
            }
            if twice <= self.dx {
                self.error += self.dx;
                self.y += self.sy;
            }
        }
        Some(result)
    }
}

/// Rasterizes incrementally; memory is bounded by input vertices and one pixel batch.
pub struct PixelBatches {
    segments: Vec<Vec<(i64, i64)>>,
    width: i64,
    segment: usize,
    point: usize,
    line: Option<Line>,
}

impl PixelBatches {
    pub fn new(segments: Vec<Vec<(f64, f64)>>, zoom: u8) -> Option<Self> {
        if zoom > 20 {
            return None;
        }
        let width = 256_i64 << zoom;
        let segments = segments
            .into_iter()
            .map(|segment| {
                segment
                    .into_iter()
                    .map(|(longitude, latitude)| {
                        if !longitude.is_finite()
                            || !latitude.is_finite()
                            || !(-180.0..=180.0).contains(&longitude)
                            || !(-90.0..=90.0).contains(&latitude)
                        {
                            return None;
                        }
                        let latitude = latitude.clamp(-MAX_LATITUDE, MAX_LATITUDE).to_radians();
                        let x = (((longitude + 180.0) / 360.0 * width as f64).floor() as i64)
                            .rem_euclid(width);
                        let y = (((1.0 - latitude.tan().asinh() / std::f64::consts::PI) / 2.0
                            * width as f64)
                            .floor() as i64)
                            .clamp(0, width - 1);
                        Some((x, y))
                    })
                    .collect::<Option<Vec<_>>>()
            })
            .collect::<Option<Vec<_>>>()?;
        Some(Self {
            segments,
            width,
            segment: 0,
            point: 0,
            line: None,
        })
    }

    fn next_pixel(&mut self) -> Option<(u32, u32)> {
        loop {
            if let Some(line) = &mut self.line {
                if let Some((x, y)) = line.next() {
                    return Some((x.rem_euclid(self.width) as u32, y as u32));
                }
                self.line = None;
            }
            let segment = self.segments.get(self.segment)?;
            if self.point == segment.len() {
                self.segment += 1;
                self.point = 0;
                continue;
            }
            let b = segment[self.point];
            let a = if self.point == 0 {
                b
            } else {
                segment[self.point - 1]
            };
            self.point += 1;
            self.line = Some(Line::new(a, b, self.width));
        }
    }
}

impl Iterator for PixelBatches {
    type Item = Vec<(u32, u32)>;
    fn next(&mut self) -> Option<Self::Item> {
        let mut pixels = BTreeSet::new();
        for _ in 0..BATCH_STEPS {
            match self.next_pixel() {
                Some(pixel) => {
                    pixels.insert(pixel);
                }
                None => break,
            }
        }
        if pixels.is_empty() {
            None
        } else {
            Some(pixels.into_iter().collect())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn pixels(segments: Vec<Vec<(f64, f64)>>) -> BTreeSet<(u32, u32)> {
        PixelBatches::new(segments, 4).unwrap().flatten().collect()
    }
    #[test]
    fn preserves_segment_breaks() {
        assert_eq!(pixels(vec![vec![(-90.0, 0.0)], vec![(90.0, 0.0)]]).len(), 2);
    }
    #[test]
    fn repeated_points_are_deduplicated_within_batch() {
        assert_eq!(
            pixels(vec![vec![(0.0, 0.0); 3]]),
            BTreeSet::from([(2048, 2048)])
        );
    }
    #[test]
    fn polar_coordinates_stay_inside_world() {
        assert_eq!(
            pixels(vec![vec![(0.0, 90.0)], vec![(0.0, -90.0)]]),
            BTreeSet::from([(2048, 0), (2048, 4095)])
        );
    }
    #[test]
    fn empty_segments_do_not_end_the_iterator() {
        assert_eq!(
            pixels(vec![vec![], vec![(0.0, 0.0)], vec![]]),
            BTreeSet::from([(2048, 2048)])
        );
    }
    #[test]
    fn reverse_wrapped_line() {
        let a = (179.0, 32.0);
        let b = (-179.0, 33.0);
        assert_eq!(pixels(vec![vec![a, b]]), pixels(vec![vec![b, a]]));
    }
    #[test]
    fn long_trace_streams_without_total_limit() {
        let batches = PixelBatches::new(vec![vec![(-90.0, 0.0), (0.0, 0.0)]], 14).unwrap();
        let mut count = 0;
        let mut calls = 0;
        for batch in batches {
            assert!(batch.len() <= BATCH_STEPS);
            count += batch.len();
            calls += 1;
        }
        assert!(count > 1_000_000);
        assert!(calls > 100);
    }
    #[test]
    fn invalid_is_rejected_before_any_batch() {
        assert!(PixelBatches::new(vec![vec![(0.0, 0.0), (f64::NAN, 0.0)]], 4).is_none());
    }
}
