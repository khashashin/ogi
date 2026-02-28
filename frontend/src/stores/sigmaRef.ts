import type Sigma from "sigma";

/** Simple module-level ref to the active Sigma instance. */
let _sigma: Sigma | null = null;

export function setSigmaRef(sigma: Sigma | null): void {
  _sigma = sigma;
}

export function getSigmaRef(): Sigma | null {
  return _sigma;
}
