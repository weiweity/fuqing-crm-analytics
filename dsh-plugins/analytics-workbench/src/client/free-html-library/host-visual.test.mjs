import test from 'node:test';
import assert from 'node:assert/strict';
import { contrastReport, estimateIframeContentWidth, inspectPage, WIDTH_MATRIX, widthBand } from './host-visual.mjs';

test('dark host body ink/lilac meet 4.5:1; brand purple is not a body promise', () => {
  const report = contrastReport({
    color: { background: '#09050D', ink: '#FEFCFF', brandSecondary: '#D3C3E8', brandPrimary: '#805D9D', brandAccent: '#F2FFDC', danger: '#FF7D91' },
  });
  const ink = report.rows.find(row => row.role === 'body-ink');
  const lilac = report.rows.find(row => row.role === 'body-lilac');
  const purple = report.rows.find(row => row.role === 'large-purple');
  assert.equal(ink.pass, true, `ink ${ink.ratio}`);
  assert.equal(lilac.pass, true, `lilac ${lilac.ratio}`);
  assert.equal(purple.bodyForbidden, true);
  assert.ok(purple.ratio >= 3, `purple ${purple.ratio}`);
  const light = contrastReport({
    color: { background: '#FEFCFF', ink: '#09050D', brandSecondary: '#674482', brandPrimary: '#805D9D', brandAccent: '#805D9D', danger: '#AB2944' },
  });
  assert.equal(light.rows.find(row => row.role === 'body-ink').pass, true);
});

test('width matrix records iframe content width and 1280 collapses rail', () => {
  assert.equal(widthBand(1280), 'desktop-1280');
  assert.equal(widthBand(375), 'phone-375');
  const side = estimateIframeContentWidth({ viewportWidth: 1440, railOpen: true, panelOpen: true });
  const closed = estimateIframeContentWidth({ viewportWidth: 1440, railOpen: true, panelOpen: false });
  assert.ok(side.iframeContentWidth < closed.iframeContentWidth);
  assert.equal(WIDTH_MATRIX.length, 9);
  assert.ok(WIDTH_MATRIX.every(row => Number.isFinite(row.iframeContentWidth)));
  const phoneOverlay = estimateIframeContentWidth({ viewportWidth: 375, railOpen: false, panelOpen: true });
  const phone = estimateIframeContentWidth({ viewportWidth: 375, railOpen: false, panelOpen: false });
  assert.equal(phoneOverlay.iframeContentWidth, phone.iframeContentWidth, 'phone overlay must not shrink iframe chrome');
});

test('page inspection never blocks generate or rewrites source', () => {
  const result = inspectPage({
    host: { landmarks: true, nativeChat: true, statusSpineVisible: true, keyboard: true },
    page: { focusableActions: true, textStatus: true, chartAlternative: false, canvasUnknown: true },
  });
  assert.equal(result.blocksGenerate, false);
  assert.equal(result.silentRewrite, false);
  assert.equal(result.hostVerdict, 'HOST_PASS');
  assert.equal(result.pageVerdict, 'PAGE_LIMITATION');
  const hostGap = inspectPage({
    host: { landmarks: false, nativeChat: true, statusSpineVisible: true, keyboard: true },
    page: { focusableActions: true, textStatus: true, chartAlternative: true },
  });
  assert.equal(hostGap.hostVerdict, 'HOST_INCOMPLETE');
  assert.notEqual(hostGap.hostVerdict, hostGap.pageVerdict);
});
