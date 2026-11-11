//! Canonical major.minor.patch compatibility, shared by commands and discovery.
pub fn parse(value: &str) -> Option<[u32; 3]> {
    if value.len() > 29 { return None; }
    let parts: Vec<_> = value.split('.').collect();
    if parts.len() != 3 { return None; }
    let mut result = [0; 3];
    for (index, part) in parts.into_iter().enumerate() {
        if part.is_empty() || part.len() > 9 || !part.bytes().all(|c| c.is_ascii_digit())
            || (part.len() > 1 && part.starts_with('0')) { return None; }
        result[index] = part.parse().ok()?;
    }
    Some(result)
}

pub fn compatible(remote: &str, local: &str) -> bool {
    matches!((parse(remote), parse(local)), (Some(a), Some(b)) if a[..2] == b[..2])
}

pub fn client_version_error(client: Option<&str>, host: &str) -> Option<String> {
    let (Some(a), Some(b)) = (client.and_then(parse), parse(host)) else {
        return Some("Missing or malformed protocol version; install matching FrameViz runtime and SDK/Viewer.".into());
    };
    if a[..2] == b[..2] { return None; }
    if a[..2] < b[..2] { Some(format!("Client protocol {} is older than Host {host}. Upgrade the SDK/Viewer.", client.unwrap())) }
    else { Some(format!("Client protocol {} is newer than Host {host}. Upgrade the FrameViz runtime.", client.unwrap())) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn series_is_canonical_and_patch_independent() {
        for version in ["0.5.0", "0.5.1", "0.5.999999999"] { assert!(compatible(version,"0.5.0")); }
        for version in ["0.4.9", "0.6.0", "00.5.1", "0.5.01", "0.5.1-beta", "0.5.1000000000", "0.5", ""] {
            assert!(!compatible(version,"0.5.0"));
        }
    }
}
