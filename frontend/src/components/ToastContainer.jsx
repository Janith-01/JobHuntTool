export default function ToastContainer({ toasts }) {
    return (
        <div className="toast-container">
            {toasts.map(toast => (
                <div key={toast.id} className={`toast ${toast.type}`}>
                    <span>{toast.message}</span>
                </div>
            ))}
        </div>
    );
}
