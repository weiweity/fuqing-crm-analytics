import { Component, createElement } from 'react';

/** Keep the overlay dialog mounted if a child panel throws while switching. */
export class OverlayErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error: error?.message || 'render-failed' };
  }

  componentDidUpdate(prev) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return createElement(
        'p',
        { role: 'alert', 'data-testid': 'sm-overlay-render-error' },
        `看板渲染失败，驾驶舱仍打开。${this.state.error}`,
      );
    }
    return this.props.children;
  }
}
