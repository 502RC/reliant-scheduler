import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { credentials } from "@/services/api";
import { useApi } from "@/hooks/useApi";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import type { CredentialFieldDefinition, CredentialTemplate } from "@/types/api";

export default function CredentialForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [credentialType, setCredentialType] = useState("");
  const [fieldValues, setFieldValues] = useState<Record<string, string | number | boolean>>({});
  const [secretFields, setSecretFields] = useState<string[]>([]);
  const [changedSecrets, setChangedSecrets] = useState<Set<string>>(new Set());
  const [customFields, setCustomFields] = useState<{ name: string; field_type: string; is_secret: boolean }[]>([]);
  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldType, setNewFieldType] = useState("string");
  const [newFieldSecret, setNewFieldSecret] = useState(false);

  // Fetch available templates
  const templatesResult = useApi(() => credentials.templates(), []);
  const templates: CredentialTemplate[] = templatesResult.data ?? [];

  // Get the selected template's field definitions
  const selectedTemplate = templates.find((t) => t.type_key === credentialType);

  // Load existing credential when editing
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    credentials.get(id).then((cred) => {
      if (cancelled) return;
      setName(cred.name);
      setDescription(cred.description ?? "");
      setCredentialType(cred.credential_type);
      setFieldValues(cred.fields as Record<string, string | number | boolean> ?? {});
      setSecretFields(cred.secret_fields);
      setLoading(false);
    }).catch((err) => {
      if (!cancelled) {
        setError(err instanceof Error ? err.message : "Failed to load credential");
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [id]);

  function handleFieldChange(fieldName: string, value: string | number | boolean) {
    setFieldValues((prev) => ({ ...prev, [fieldName]: value }));
  }

  function handleAddCustomField() {
    const trimmed = newFieldName.trim().replace(/\s+/g, "_").toLowerCase();
    if (!trimmed) return;
    if (customFields.some((f) => f.name === trimmed)) return;
    setCustomFields((prev) => [...prev, { name: trimmed, field_type: newFieldType, is_secret: newFieldSecret }]);
    setNewFieldName("");
    setNewFieldType("string");
    setNewFieldSecret(false);
  }

  function handleRemoveCustomField(fieldName: string) {
    setCustomFields((prev) => prev.filter((f) => f.name !== fieldName));
    setFieldValues((prev) => {
      const copy = { ...prev };
      delete copy[fieldName];
      return copy;
    });
  }

  function handleSecretToggle(fieldName: string) {
    setChangedSecrets((prev) => {
      const next = new Set(prev);
      if (next.has(fieldName)) {
        next.delete(fieldName);
        // Remove the value from fieldValues when untoggling
        setFieldValues((fv) => {
          const copy = { ...fv };
          delete copy[fieldName];
          return copy;
        });
      } else {
        next.add(fieldName);
      }
      return next;
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    try {
      if (isEdit && id) {
        // Only send changed fields. For secrets, only include if "Change" was toggled.
        const updateFields: Record<string, string | number | boolean> = {};
        for (const [key, value] of Object.entries(fieldValues)) {
          const isSecret = secretFields.includes(key) ||
            selectedTemplate?.fields.find((f) => f.name === key)?.is_secret;
          if (isSecret && !changedSecrets.has(key)) continue;
          updateFields[key] = value;
        }
        await credentials.update(id, {
          name,
          description: description || null,
          fields: Object.keys(updateFields).length > 0 ? updateFields : undefined,
        });
        navigate("/credentials");
      } else {
        await credentials.create({
          name,
          credential_type: credentialType as any,
          description: description || null,
          fields: fieldValues,
        });
        navigate("/credentials");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save credential");
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner message="Loading credential..." />;

  return (
    <>
      <div className="page-header">
        <h2>{isEdit ? "Edit Credential" : "New Credential"}</h2>
      </div>

      <div className="card" style={{ padding: 24, maxWidth: 720 }}>
        {error && (
          <div role="alert" className="form-error" style={{ marginBottom: 16, padding: 12, background: "#fef2f2", borderRadius: 6 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="cred-name">Name *</label>
            <input
              id="cred-name"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. Windows Admin - CUROHS"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="cred-description">Description</label>
            <textarea
              id="cred-description"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this credential used for?"
            />
          </div>

          {!isEdit && (
            <div className="form-group">
              <label className="form-label" htmlFor="cred-type">Credential Type *</label>
              <select
                id="cred-type"
                className="form-select"
                value={credentialType}
                onChange={(e) => {
                  setCredentialType(e.target.value);
                  setFieldValues({});
                }}
                required
              >
                <option value="">Select a type...</option>
                {templates.map((t) => (
                  <option key={t.type_key} value={t.type_key}>{t.display_name}</option>
                ))}
              </select>
              {selectedTemplate && (
                <div className="form-hint" style={{ marginTop: 4 }}>
                  {selectedTemplate.description}
                </div>
              )}
            </div>
          )}

          {isEdit && credentialType && (
            <div className="form-group">
              <label className="form-label">Type</label>
              <div style={{ padding: "8px 0", color: "#6b7280" }}>
                {templates.find((t) => t.type_key === credentialType)?.display_name ?? credentialType}
              </div>
            </div>
          )}

          {selectedTemplate && selectedTemplate.fields.length > 0 && (
            <div style={{ borderTop: "1px solid #e5e7eb", marginTop: 16, paddingTop: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#374151" }}>
                Configuration
              </h3>
              {selectedTemplate.fields.map((field) => (
                <DynamicField
                  key={field.name}
                  field={field}
                  value={fieldValues[field.name]}
                  onChange={(val) => handleFieldChange(field.name, val)}
                  isEdit={isEdit}
                  isSecretStored={secretFields.includes(field.name)}
                  isSecretChanged={changedSecrets.has(field.name)}
                  onSecretToggle={() => handleSecretToggle(field.name)}
                />
              ))}
            </div>
          )}

          {credentialType === "custom" && (
            <div style={{ borderTop: "1px solid #e5e7eb", marginTop: 16, paddingTop: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#374151" }}>
                Custom Fields
              </h3>

              {customFields.map((cf) => (
                <div key={cf.name} style={{ marginBottom: 12 }}>
                  <DynamicField
                    field={{
                      name: cf.name,
                      label: cf.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
                      field_type: cf.is_secret ? "password" : cf.field_type as any,
                      required: false,
                      is_secret: cf.is_secret,
                      default: null,
                      placeholder: null,
                      options: null,
                    }}
                    value={fieldValues[cf.name]}
                    onChange={(val) => handleFieldChange(cf.name, val)}
                    isEdit={isEdit}
                    isSecretStored={secretFields.includes(cf.name)}
                    isSecretChanged={changedSecrets.has(cf.name)}
                    onSecretToggle={() => handleSecretToggle(cf.name)}
                  />
                  {!isEdit && (
                    <button
                      type="button"
                      onClick={() => handleRemoveCustomField(cf.name)}
                      style={{ fontSize: 12, color: "#dc2626", background: "none", border: "none", cursor: "pointer", marginTop: -8 }}
                    >
                      Remove field
                    </button>
                  )}
                </div>
              ))}

              <div style={{ display: "flex", gap: 8, alignItems: "flex-end", padding: 12, background: "#f9fafb", borderRadius: 8, marginTop: 8 }}>
                <div style={{ flex: 1 }}>
                  <label className="form-label" style={{ fontSize: 12 }}>Field Name</label>
                  <input
                    className="form-input"
                    value={newFieldName}
                    onChange={(e) => setNewFieldName(e.target.value)}
                    placeholder="e.g. api_token"
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddCustomField(); } }}
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: 12 }}>Type</label>
                  <select
                    className="form-select"
                    value={newFieldType}
                    onChange={(e) => setNewFieldType(e.target.value)}
                    style={{ minWidth: 100 }}
                  >
                    <option value="string">Text</option>
                    <option value="password">Password</option>
                    <option value="textarea">Multi-line</option>
                    <option value="number">Number</option>
                    <option value="boolean">Toggle</option>
                  </select>
                </div>
                <div>
                  <label className="form-label" style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, cursor: "pointer", whiteSpace: "nowrap" }}>
                    <input
                      type="checkbox"
                      checked={newFieldSecret}
                      onChange={(e) => setNewFieldSecret(e.target.checked)}
                    />
                    Secret
                  </label>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleAddCustomField}
                  disabled={!newFieldName.trim()}
                >
                  + Add
                </button>
              </div>

              {customFields.length === 0 && (
                <p style={{ color: "#9ca3af", fontSize: 13, marginTop: 8 }}>
                  Add fields above to define your custom credential structure. Fields marked as "Secret" will be stored in Azure Key Vault.
                </p>
              )}
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 24 }}>
            <button type="submit" className="btn btn-primary" disabled={saving || !name || (!isEdit && !credentialType)}>
              {saving ? "Saving..." : isEdit ? "Update Credential" : "Create Credential"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/credentials")}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </>
  );
}

function DynamicField({
  field,
  value,
  onChange,
  isEdit,
  isSecretStored,
  isSecretChanged,
  onSecretToggle,
}: {
  field: CredentialFieldDefinition;
  value: string | number | boolean | undefined;
  onChange: (value: string | number | boolean) => void;
  isEdit: boolean;
  isSecretStored: boolean;
  isSecretChanged: boolean;
  onSecretToggle: () => void;
}) {
  const fieldId = `cred-field-${field.name}`;

  // In edit mode, secret fields show masked unless "Change" is toggled
  if (isEdit && field.is_secret && isSecretStored && !isSecretChanged) {
    return (
      <div className="form-group">
        <label className="form-label" htmlFor={fieldId}>
          {field.label} {field.required && "*"}
          <span style={{ marginLeft: 8, fontSize: 11, color: "#6b7280" }}>🔒 stored in Key Vault</span>
        </label>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="form-input"
            value="••••••••••••"
            disabled
            style={{ flex: 1, color: "#9ca3af" }}
          />
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onSecretToggle}
          >
            Change
          </button>
        </div>
      </div>
    );
  }

  const label = (
    <label className="form-label" htmlFor={fieldId}>
      {field.label} {field.required && "*"}
      {field.is_secret && <span style={{ marginLeft: 8, fontSize: 11, color: "#dc2626" }}>🔒 secret</span>}
    </label>
  );

  switch (field.field_type) {
    case "password":
      return (
        <div className="form-group">
          {label}
          <div style={{ display: "flex", gap: 8 }}>
            <input
              id={fieldId}
              className="form-input"
              type="password"
              value={(value as string) ?? ""}
              onChange={(e) => onChange(e.target.value)}
              required={field.required && !isEdit}
              placeholder={field.placeholder ?? ""}
              style={{ flex: 1 }}
            />
            {isEdit && isSecretChanged && (
              <button type="button" className="btn btn-secondary btn-sm" onClick={onSecretToggle}>
                Cancel
              </button>
            )}
          </div>
        </div>
      );

    case "textarea":
      return (
        <div className="form-group">
          {label}
          <textarea
            id={fieldId}
            className="form-textarea"
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
            required={field.required && !isEdit}
            placeholder={field.placeholder ?? ""}
            style={{ fontFamily: "monospace", minHeight: 80 }}
          />
        </div>
      );

    case "number":
      return (
        <div className="form-group">
          {label}
          <input
            id={fieldId}
            className="form-input"
            type="number"
            value={(value as number) ?? (field.default ? Number(field.default) : "")}
            onChange={(e) => onChange(Number(e.target.value))}
            placeholder={field.placeholder ?? ""}
          />
        </div>
      );

    case "boolean":
      return (
        <div className="form-group">
          <label className="form-label" style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={value !== undefined ? Boolean(value) : field.default === "true"}
              onChange={(e) => onChange(e.target.checked)}
            />
            {field.label}
          </label>
        </div>
      );

    case "select":
      return (
        <div className="form-group">
          {label}
          <select
            id={fieldId}
            className="form-select"
            value={(value as string) ?? field.default ?? ""}
            onChange={(e) => onChange(e.target.value)}
          >
            {field.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      );

    default: // string
      return (
        <div className="form-group">
          {label}
          <input
            id={fieldId}
            className="form-input"
            type="text"
            value={(value as string) ?? field.default ?? ""}
            onChange={(e) => onChange(e.target.value)}
            required={field.required && !isEdit}
            placeholder={field.placeholder ?? ""}
          />
        </div>
      );
  }
}
