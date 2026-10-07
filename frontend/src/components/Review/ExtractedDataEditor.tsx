import React from 'react'

interface ExtractedDataEditorProps {
  documentType: string | null
  data: Record<string, any>
  onChange: (updated: Record<string, any>) => void
  disabled?: boolean
}

export const ExtractedDataEditor: React.FC<ExtractedDataEditorProps> = ({
  documentType,
  data,
  onChange,
  disabled = false,
}) => {
  const docTypeUpper = (documentType || 'OTHER').toUpperCase()

  const handleFieldChange = (field: string, value: any) => {
    onChange({
      ...data,
      [field]: value,
    })
  }

  const handleNestedFieldChange = (parent: string, field: string, value: any) => {
    const parentObj = data[parent] || {}
    onChange({
      ...data,
      [parent]: {
        ...parentObj,
        [field]: value,
      },
    })
  }

  // --- Invoice Editor ---
  if (docTypeUpper === 'INVOICE') {
    const vendor = data.vendor || {}
    const customer = data.customer || {}
    const lineItems: any[] = Array.isArray(data.line_items) ? data.line_items : []

    const handleLineItemChange = (index: number, field: string, val: any) => {
      const nextItems = [...lineItems]
      nextItems[index] = {
        ...nextItems[index],
        [field]: field === 'quantity' || field === 'unit_price' || field === 'tax' || field === 'amount'
          ? (val === '' ? null : Number(val))
          : val,
      }
      onChange({ ...data, line_items: nextItems })
    }

    const addLineItem = () => {
      onChange({
        ...data,
        line_items: [
          ...lineItems,
          { description: 'New item', quantity: 1, unit_price: 0, tax: 0, amount: 0 },
        ],
      })
    }

    const removeLineItem = (index: number) => {
      onChange({
        ...data,
        line_items: lineItems.filter((_, i) => i !== index),
      })
    }

    return (
      <div className="editor-section">
        <h4 style={{ color: 'var(--color-accent-primary)', marginBottom: '8px' }}>Invoice Details</h4>
        <div className="field-grid">
          <div className="input-group">
            <label className="input-label">Invoice Number</label>
            <input
              type="text"
              className="input-field"
              value={data.invoice_number ?? ''}
              onChange={(e) => handleFieldChange('invoice_number', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Invoice Date</label>
            <input
              type="text"
              className="input-field"
              value={data.invoice_date ?? ''}
              placeholder="YYYY-MM-DD"
              onChange={(e) => handleFieldChange('invoice_date', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Due Date</label>
            <input
              type="text"
              className="input-field"
              value={data.due_date ?? ''}
              placeholder="YYYY-MM-DD"
              onChange={(e) => handleFieldChange('due_date', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Currency</label>
            <input
              type="text"
              className="input-field"
              value={data.currency ?? 'USD'}
              onChange={(e) => handleFieldChange('currency', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Subtotal</label>
            <input
              type="number"
              step="0.01"
              className="input-field"
              value={data.subtotal ?? ''}
              onChange={(e) => handleFieldChange('subtotal', e.target.value === '' ? null : Number(e.target.value))}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Tax Amount</label>
            <input
              type="number"
              step="0.01"
              className="input-field"
              value={data.tax_amount ?? ''}
              onChange={(e) => handleFieldChange('tax_amount', e.target.value === '' ? null : Number(e.target.value))}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label" style={{ fontWeight: 'bold', color: 'var(--color-text-primary)' }}>Total Amount *</label>
            <input
              type="number"
              step="0.01"
              className="input-field"
              value={data.total_amount ?? ''}
              onChange={(e) => handleFieldChange('total_amount', e.target.value === '' ? null : Number(e.target.value))}
              disabled={disabled}
            />
          </div>
        </div>

        {/* Vendor & Customer */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '16px' }}>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px' }}>
            <h5 style={{ color: '#93c5fd', marginBottom: '8px' }}>Vendor Information</h5>
            <div className="input-group" style={{ marginBottom: '8px' }}>
              <label className="input-label">Vendor Name</label>
              <input
                type="text"
                className="input-field"
                value={vendor.name ?? ''}
                onChange={(e) => handleNestedFieldChange('vendor', 'name', e.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="input-group" style={{ marginBottom: '8px' }}>
              <label className="input-label">Tax ID / VAT</label>
              <input
                type="text"
                className="input-field"
                value={vendor.tax_id ?? ''}
                onChange={(e) => handleNestedFieldChange('vendor', 'tax_id', e.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="input-group">
              <label className="input-label">Address</label>
              <input
                type="text"
                className="input-field"
                value={vendor.address ?? ''}
                onChange={(e) => handleNestedFieldChange('vendor', 'address', e.target.value)}
                disabled={disabled}
              />
            </div>
          </div>

          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px' }}>
            <h5 style={{ color: '#93c5fd', marginBottom: '8px' }}>Customer Information</h5>
            <div className="input-group" style={{ marginBottom: '8px' }}>
              <label className="input-label">Customer Name</label>
              <input
                type="text"
                className="input-field"
                value={customer.name ?? ''}
                onChange={(e) => handleNestedFieldChange('customer', 'name', e.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="input-group" style={{ marginBottom: '8px' }}>
              <label className="input-label">Customer Email</label>
              <input
                type="email"
                className="input-field"
                value={customer.email ?? ''}
                onChange={(e) => handleNestedFieldChange('customer', 'email', e.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="input-group">
              <label className="input-label">Address</label>
              <input
                type="text"
                className="input-field"
                value={customer.address ?? ''}
                onChange={(e) => handleNestedFieldChange('customer', 'address', e.target.value)}
                disabled={disabled}
              />
            </div>
          </div>
        </div>

        {/* Line Items */}
        <div style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h5 style={{ color: '#93c5fd' }}>Line Items ({lineItems.length})</h5>
            {!disabled && (
              <button type="button" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }} onClick={addLineItem}>
                + Add Item
              </button>
            )}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="line-items-table">
              <thead>
                <tr>
                  <th>Description</th>
                  <th style={{ width: '80px' }}>Qty</th>
                  <th style={{ width: '100px' }}>Price</th>
                  <th style={{ width: '100px' }}>Total</th>
                  {!disabled && <th style={{ width: '50px' }}></th>}
                </tr>
              </thead>
              <tbody>
                {lineItems.map((item, idx) => (
                  <tr key={idx}>
                    <td>
                      <input
                        type="text"
                        className="input-field"
                        style={{ width: '100%' }}
                        value={item.description ?? ''}
                        onChange={(e) => handleLineItemChange(idx, 'description', e.target.value)}
                        disabled={disabled}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        step="any"
                        className="input-field"
                        style={{ width: '100%' }}
                        value={item.quantity ?? ''}
                        onChange={(e) => handleLineItemChange(idx, 'quantity', e.target.value)}
                        disabled={disabled}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.01"
                        className="input-field"
                        style={{ width: '100%' }}
                        value={item.unit_price ?? ''}
                        onChange={(e) => handleLineItemChange(idx, 'unit_price', e.target.value)}
                        disabled={disabled}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.01"
                        className="input-field"
                        style={{ width: '100%' }}
                        value={item.amount ?? item.total_amount ?? ''}
                        onChange={(e) => handleLineItemChange(idx, 'amount', e.target.value)}
                        disabled={disabled}
                      />
                    </td>
                    {!disabled && (
                      <td>
                        <button
                          type="button"
                          className="btn btn-danger"
                          style={{ padding: '2px 8px', fontSize: '11px' }}
                          onClick={() => removeLineItem(idx)}
                        >
                          ✕
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  // --- Receipt Editor ---
  if (docTypeUpper === 'RECEIPT') {
    const merchant = data.merchant || {}
    const items: any[] = Array.isArray(data.items) ? data.items : []

    const handleItemChange = (index: number, field: string, val: any) => {
      const nextItems = [...items]
      nextItems[index] = {
        ...nextItems[index],
        [field]: field === 'quantity' || field === 'unit_price' || field === 'amount'
          ? (val === '' ? null : Number(val))
          : val,
      }
      onChange({ ...data, items: nextItems })
    }

    const addItem = () => {
      onChange({
        ...data,
        items: [...items, { description: 'Item', quantity: 1, unit_price: 0, amount: 0 }],
      })
    }

    const removeItem = (index: number) => {
      onChange({ ...data, items: items.filter((_, i) => i !== index) })
    }

    return (
      <div className="editor-section">
        <h4 style={{ color: 'var(--color-accent-primary)', marginBottom: '8px' }}>Receipt Details</h4>
        <div className="field-grid">
          <div className="input-group">
            <label className="input-label">Receipt Number</label>
            <input
              type="text"
              className="input-field"
              value={data.receipt_number ?? ''}
              onChange={(e) => handleFieldChange('receipt_number', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Merchant Name</label>
            <input
              type="text"
              className="input-field"
              value={merchant.name ?? ''}
              onChange={(e) => handleNestedFieldChange('merchant', 'name', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Transaction Date</label>
            <input
              type="text"
              className="input-field"
              value={data.transaction_date ?? ''}
              placeholder="YYYY-MM-DD"
              onChange={(e) => handleFieldChange('transaction_date', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Payment Method</label>
            <input
              type="text"
              className="input-field"
              value={data.payment_method ?? ''}
              onChange={(e) => handleFieldChange('payment_method', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Tax Amount</label>
            <input
              type="number"
              step="0.01"
              className="input-field"
              value={data.tax_amount ?? ''}
              onChange={(e) => handleFieldChange('tax_amount', e.target.value === '' ? null : Number(e.target.value))}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label" style={{ fontWeight: 'bold' }}>Total Amount *</label>
            <input
              type="number"
              step="0.01"
              className="input-field"
              value={data.total_amount ?? ''}
              onChange={(e) => handleFieldChange('total_amount', e.target.value === '' ? null : Number(e.target.value))}
              disabled={disabled}
            />
          </div>
        </div>

        {/* Items */}
        <div style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h5 style={{ color: '#93c5fd' }}>Purchased Items ({items.length})</h5>
            {!disabled && (
              <button type="button" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }} onClick={addItem}>
                + Add Item
              </button>
            )}
          </div>
          <table className="line-items-table">
            <thead>
              <tr>
                <th>Description</th>
                <th style={{ width: '80px' }}>Qty</th>
                <th style={{ width: '100px' }}>Unit Price</th>
                <th style={{ width: '100px' }}>Amount</th>
                {!disabled && <th style={{ width: '50px' }}></th>}
              </tr>
            </thead>
            <tbody>
              {items.map((it, idx) => (
                <tr key={idx}>
                  <td>
                    <input
                      type="text"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={it.description ?? ''}
                      onChange={(e) => handleItemChange(idx, 'description', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="any"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={it.quantity ?? ''}
                      onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={it.unit_price ?? ''}
                      onChange={(e) => handleItemChange(idx, 'unit_price', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={it.amount ?? ''}
                      onChange={(e) => handleItemChange(idx, 'amount', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  {!disabled && (
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '2px 8px', fontSize: '11px' }}
                        onClick={() => removeItem(idx)}
                      >
                        ✕
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // --- Purchase Order Editor ---
  if (docTypeUpper === 'PURCHASE_ORDER') {
    const buyer = data.buyer || {}
    const supplier = data.supplier || {}
    const lineItems: any[] = Array.isArray(data.line_items) ? data.line_items : []

    const handlePoItemChange = (index: number, field: string, val: any) => {
      const nextItems = [...lineItems]
      nextItems[index] = {
        ...nextItems[index],
        [field]: field === 'quantity' || field === 'unit_price' || field === 'total_amount'
          ? (val === '' ? null : Number(val))
          : val,
      }
      onChange({ ...data, line_items: nextItems })
    }

    return (
      <div className="editor-section">
        <h4 style={{ color: 'var(--color-accent-primary)', marginBottom: '8px' }}>Purchase Order Details</h4>
        <div className="field-grid">
          <div className="input-group">
            <label className="input-label">PO Number *</label>
            <input
              type="text"
              className="input-field"
              value={data.po_number ?? ''}
              onChange={(e) => handleFieldChange('po_number', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">PO Date</label>
            <input
              type="text"
              className="input-field"
              value={data.po_date ?? ''}
              placeholder="YYYY-MM-DD"
              onChange={(e) => handleFieldChange('po_date', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Delivery Date</label>
            <input
              type="text"
              className="input-field"
              value={data.delivery_date ?? ''}
              placeholder="YYYY-MM-DD"
              onChange={(e) => handleFieldChange('delivery_date', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Total Amount *</label>
            <input
              type="number"
              step="0.01"
              className="input-field"
              value={data.total_amount ?? ''}
              onChange={(e) => handleFieldChange('total_amount', e.target.value === '' ? null : Number(e.target.value))}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Buyer Name</label>
            <input
              type="text"
              className="input-field"
              value={buyer.name ?? ''}
              onChange={(e) => handleNestedFieldChange('buyer', 'name', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Supplier Name</label>
            <input
              type="text"
              className="input-field"
              value={supplier.name ?? ''}
              onChange={(e) => handleNestedFieldChange('supplier', 'name', e.target.value)}
              disabled={disabled}
            />
          </div>
        </div>

        <div style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h5 style={{ color: '#93c5fd' }}>PO Line Items ({lineItems.length})</h5>
            {!disabled && (
              <button
                type="button"
                className="btn btn-secondary"
                style={{ padding: '4px 10px', fontSize: '12px' }}
                onClick={() =>
                  onChange({
                    ...data,
                    line_items: [
                      ...lineItems,
                      { description: 'Item', quantity: 1, unit_price: 0, total_amount: 0 },
                    ],
                  })
                }
              >
                + Add Item
              </button>
            )}
          </div>
          <table className="line-items-table">
            <thead>
              <tr>
                <th>Description</th>
                <th style={{ width: '80px' }}>Qty</th>
                <th style={{ width: '100px' }}>Unit Price</th>
                <th style={{ width: '100px' }}>Total Amount</th>
                {!disabled && <th style={{ width: '50px' }}></th>}
              </tr>
            </thead>
            <tbody>
              {lineItems.map((it, idx) => (
                <tr key={idx}>
                  <td>
                    <input
                      type="text"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={it.description ?? ''}
                      onChange={(e) => handlePoItemChange(idx, 'description', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="any"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={it.quantity ?? ''}
                      onChange={(e) => handlePoItemChange(idx, 'quantity', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={it.unit_price ?? ''}
                      onChange={(e) => handlePoItemChange(idx, 'unit_price', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={it.total_amount ?? ''}
                      onChange={(e) => handlePoItemChange(idx, 'total_amount', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  {!disabled && (
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '2px 8px', fontSize: '11px' }}
                        onClick={() =>
                          onChange({
                            ...data,
                            line_items: lineItems.filter((_, i) => i !== idx),
                          })
                        }
                      >
                        ✕
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // --- Contract Editor ---
  if (docTypeUpper === 'CONTRACT') {
    const parties: any[] = Array.isArray(data.parties) ? data.parties : []

    const handlePartyChange = (index: number, field: string, val: string) => {
      const nextParties = [...parties]
      nextParties[index] = { ...nextParties[index], [field]: val }
      onChange({ ...data, parties: nextParties })
    }

    return (
      <div className="editor-section">
        <h4 style={{ color: 'var(--color-accent-primary)', marginBottom: '8px' }}>Contract Details</h4>
        <div className="field-grid">
          <div className="input-group">
            <label className="input-label">Contract Title *</label>
            <input
              type="text"
              className="input-field"
              value={data.contract_title ?? ''}
              onChange={(e) => handleFieldChange('contract_title', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Contract Number</label>
            <input
              type="text"
              className="input-field"
              value={data.contract_number ?? ''}
              onChange={(e) => handleFieldChange('contract_number', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Effective Date</label>
            <input
              type="text"
              className="input-field"
              value={data.effective_date ?? ''}
              placeholder="YYYY-MM-DD"
              onChange={(e) => handleFieldChange('effective_date', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Expiration Date</label>
            <input
              type="text"
              className="input-field"
              value={data.expiration_date ?? ''}
              placeholder="YYYY-MM-DD"
              onChange={(e) => handleFieldChange('expiration_date', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Governing Law</label>
            <input
              type="text"
              className="input-field"
              value={data.governing_law ?? ''}
              onChange={(e) => handleFieldChange('governing_law', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="input-group">
            <label className="input-label">Total Value</label>
            <input
              type="number"
              step="0.01"
              className="input-field"
              value={data.total_value ?? ''}
              onChange={(e) => handleFieldChange('total_value', e.target.value === '' ? null : Number(e.target.value))}
              disabled={disabled}
            />
          </div>
        </div>

        <div style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h5 style={{ color: '#93c5fd' }}>Parties ({parties.length})</h5>
            {!disabled && (
              <button
                type="button"
                className="btn btn-secondary"
                style={{ padding: '4px 10px', fontSize: '12px' }}
                onClick={() =>
                  onChange({
                    ...data,
                    parties: [...parties, { name: '', role: 'Party', jurisdiction: '' }],
                  })
                }
              >
                + Add Party
              </button>
            )}
          </div>
          <table className="line-items-table">
            <thead>
              <tr>
                <th>Entity Name</th>
                <th>Role</th>
                <th>Jurisdiction</th>
                {!disabled && <th style={{ width: '50px' }}></th>}
              </tr>
            </thead>
            <tbody>
              {parties.map((p, idx) => (
                <tr key={idx}>
                  <td>
                    <input
                      type="text"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={p.name ?? ''}
                      onChange={(e) => handlePartyChange(idx, 'name', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={p.role ?? ''}
                      onChange={(e) => handlePartyChange(idx, 'role', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      className="input-field"
                      style={{ width: '100%' }}
                      value={p.jurisdiction ?? ''}
                      onChange={(e) => handlePartyChange(idx, 'jurisdiction', e.target.value)}
                      disabled={disabled}
                    />
                  </td>
                  {!disabled && (
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '2px 8px', fontSize: '11px' }}
                        onClick={() =>
                          onChange({
                            ...data,
                            parties: parties.filter((_, i) => i !== idx),
                          })
                        }
                      >
                        ✕
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // --- Default: OTHER Editor ---
  const keyValues: any[] = Array.isArray(data.key_values) ? data.key_values : []

  const handleKvChange = (index: number, field: string, val: string) => {
    const nextKv = [...keyValues]
    nextKv[index] = { ...nextKv[index], [field]: val }
    onChange({ ...data, key_values: nextKv })
  }

  return (
    <div className="editor-section">
      <h4 style={{ color: 'var(--color-accent-primary)', marginBottom: '8px' }}>Document Extraction</h4>
      <div className="field-grid">
        <div className="input-group">
          <label className="input-label">Title</label>
          <input
            type="text"
            className="input-field"
            value={data.title ?? ''}
            onChange={(e) => handleFieldChange('title', e.target.value)}
            disabled={disabled}
          />
        </div>
      </div>
      <div className="input-group" style={{ marginTop: '12px' }}>
        <label className="input-label">Summary</label>
        <textarea
          rows={3}
          className="input-field"
          value={data.summary ?? ''}
          onChange={(e) => handleFieldChange('summary', e.target.value)}
          disabled={disabled}
        />
      </div>

      <div style={{ marginTop: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <h5 style={{ color: '#93c5fd' }}>Key-Value Pairs ({keyValues.length})</h5>
          {!disabled && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: '12px' }}
              onClick={() =>
                onChange({
                  ...data,
                  key_values: [...keyValues, { key: '', value: '' }],
                })
              }
            >
              + Add Key-Value
            </button>
          )}
        </div>
        <table className="line-items-table">
          <thead>
            <tr>
              <th style={{ width: '40%' }}>Key</th>
              <th style={{ width: '50%' }}>Value</th>
              {!disabled && <th style={{ width: '50px' }}></th>}
            </tr>
          </thead>
          <tbody>
            {keyValues.map((kv, idx) => (
              <tr key={idx}>
                <td>
                  <input
                    type="text"
                    className="input-field"
                    style={{ width: '100%' }}
                    value={kv.key ?? ''}
                    onChange={(e) => handleKvChange(idx, 'key', e.target.value)}
                    disabled={disabled}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    className="input-field"
                    style={{ width: '100%' }}
                    value={kv.value ?? ''}
                    onChange={(e) => handleKvChange(idx, 'value', e.target.value)}
                    disabled={disabled}
                  />
                </td>
                {!disabled && (
                  <td>
                    <button
                      type="button"
                      className="btn btn-danger"
                      style={{ padding: '2px 8px', fontSize: '11px' }}
                      onClick={() =>
                        onChange({
                          ...data,
                          key_values: keyValues.filter((_, i) => i !== idx),
                        })
                      }
                    >
                      ✕
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ExtractedDataEditor
