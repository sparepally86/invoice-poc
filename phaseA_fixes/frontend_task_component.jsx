// React TaskRow example showing optimistic UI update, button disabling, and SSE handling.
import React, { useState, useEffect } from 'react';

export default function TaskRow({ task, currentUser, onTaskRemoved }) {
  const [submitting, setSubmitting] = useState(false);
  const [invoiceStatus, setInvoiceStatus] = useState(task.invoice?.status || null);

  useEffect(() => {
    // Subscribe to SSE at mount. Replace with your app's event source path if different.
    const es = new EventSource('/api/v1/events');
    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'invoice:update' && msg.invoice_id === task.invoice?._id) {
          setInvoiceStatus(msg.status);
        }
        if (msg.type === 'task:update' && msg.task_id === task._id) {
          // If task completed elsewhere, remove from list
          if (msg.status === 'completed') {
            onTaskRemoved(task._id);
          }
        }
      } catch (err) {
        // ignore malformed messages
      }
    };
    return () => es.close();
  }, [task, onTaskRemoved]);

  const isTerminal = ['READY_FOR_POSTING','REJECTED','POSTED','CANCELLED'].includes(invoiceStatus);
  const disabled = submitting || task.status === 'completed' || isTerminal;

  async function handleAction(actionType) {
    setSubmitting(true);
    try {
      const res = await fetch(`/api/v1/tasks/${task._id}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionType, user: currentUser })
      });
      if (!res.ok) throw new Error('server error');
      // Remove the task from UI since it's completed and invoice reached terminal state
      onTaskRemoved(task._id);
    } catch (err) {
      console.error(err);
      // TODO: show toast / user-visible error
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <tr>
      <td>{task.invoice?.invoice_number}</td>
      <td>{task.type}</td>
      <td>
        <button disabled={disabled} onClick={() => handleAction('approve')}>Approve</button>
        <button disabled={disabled} onClick={() => handleAction('reject')}>Reject</button>
      </td>
    </tr>
  );
}