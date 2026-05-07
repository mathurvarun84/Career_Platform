import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  readonly children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  public state: ErrorBoundaryState = { hasError: false };

  public static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("Render error caught by ErrorBoundary:", error, errorInfo);
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false });
    window.location.reload();
  };

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div style={{ minHeight: "100vh", background: "#ffffff" }}>
          <div
            style={{
              maxWidth: "680px",
              margin: "80px auto",
              padding: "0 24px",
            }}
          >
            <div
              style={{
                background: "#ffffff",
                border: "1.5px solid #e5e7eb",
                borderRadius: "16px",
                padding: "28px 24px",
                textAlign: "center",
                boxShadow: "0 3px 0 #e5e7eb, 0 5px 16px rgba(0,0,0,0.05)",
              }}
            >
              <div style={{ fontSize: "18px", fontWeight: 700, color: "#111827" }}>
                Something went wrong
              </div>
              <div
                style={{
                  fontSize: "13px",
                  color: "#6b7280",
                  lineHeight: 1.6,
                  marginTop: "8px",
                }}
              >
                A rendering error interrupted this page. Retry to continue.
              </div>
              <button
                type="button"
                onClick={this.handleRetry}
                style={{
                  marginTop: "14px",
                  background: "#6366f1",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "10px",
                  padding: "10px 18px",
                  fontSize: "13px",
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: "0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.25)",
                }}
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
