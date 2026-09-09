import type { Component, ReactNode } from 'react';

export class OverlayErrorBoundary extends Component<{ resetKey?: number | string; children: ReactNode }, { error: string | null }> {}
