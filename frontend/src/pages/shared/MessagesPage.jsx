import { useCallback, useEffect, useMemo, useState } from "react";
import { MessageCircle, Send, Search, SlidersHorizontal, UserPlus, X } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { authSession, getErrorMessage } from "../../services/api";
import { messageService } from "../../services/communicationService";

const actorTypeLabels = {
  superadmin: "Super admins",
  tenant_admin: "Administrators",
  teacher: "Teachers",
  student: "Students",
  parent: "Parents",
};

const authRoleToActorType = {
  admin: "tenant_admin",
  superadmin: "superadmin",
  teacher: "teacher",
  student: "student",
  parent: "parent",
};
const CONVERSATION_PAGE_SIZE = 20;

const roleLabel = (actorType) => actorTypeLabels[actorType] || actorType.replaceAll("_", " ");
const actorKeyFor = (item) => `${item?.actor_type}:${item?.actor_id}`;
const shortActorId = (value) => (value ? String(value).slice(0, 8) : "unknown");

const decodeTokenPayload = (token) => {
  try {
    const payload = token?.split(".")?.[1];
    if (!payload) return {};
    const normalizedPayload = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padding = "=".repeat((4 - (normalizedPayload.length % 4)) % 4);
    return JSON.parse(atob(`${normalizedPayload}${padding}`));
  } catch {
    return {};
  }
};

const flattenRecipients = (groups) =>
  (groups || []).flatMap((group) =>
    (group.recipients || []).map((recipient) => ({
      ...recipient,
      group_label: recipient.group_label || group.label,
    })),
  );

const identityLabel = (identity, currentActorKey, { useSelfLabel = true } = {}) => {
  if (!identity) return "Unknown contact";
  if (useSelfLabel && actorKeyFor(identity) === currentActorKey) return "You";
  return identity.label || `${roleLabel(identity.actor_type)} ${shortActorId(identity.actor_id)}`;
};

const identityMeta = (identity) => {
  if (!identity) return "";
  const role = roleLabel(identity.actor_type);
  return identity.group_label ? `${role} - ${identity.group_label}` : role;
};

const conversationTitle = (conversation, currentActorKey, directory) => {
  if (conversation?.subject) return conversation.subject;
  const other = (conversation?.participants || []).find(
    (participant) => `${participant.actor_type}:${participant.actor_id}` !== currentActorKey,
  );
  return other ? identityLabel(directory[actorKeyFor(other)] || other, currentActorKey) : "Direct conversation";
};

const latestSenderTitle = (conversation, directory) => {
  const latestMessage = conversation?.messages?.at(-1);
  if (!latestMessage) return "No sender yet";
  const senderKey = `${latestMessage.sender_actor_type}:${latestMessage.sender_actor_id}`;
  const sender = directory[senderKey] || {
    actor_type: latestMessage.sender_actor_type,
    actor_id: latestMessage.sender_actor_id,
  };
  return identityLabel(sender, "", { useSelfLabel: false });
};

const currentUserLabel = (user, actorType, actorId) => {
  if (actorType === "student") return user.admission_number || user.student_number || user.email || shortActorId(actorId);
  if (actorType === "teacher") return user.staff_id || user.email || shortActorId(actorId);
  return user.email || shortActorId(actorId);
};

const latestSenderMeta = (conversation, currentActorKey, directory) => {
  const latestMessage = conversation?.messages?.at(-1);
  if (!latestMessage) return "No messages yet";
  const senderKey = `${latestMessage.sender_actor_type}:${latestMessage.sender_actor_id}`;
  if (senderKey === currentActorKey) return "You sent";
  const sender = directory[senderKey] || {
    actor_type: latestMessage.sender_actor_type,
    actor_id: latestMessage.sender_actor_id,
  };
  return `${roleLabel(sender.actor_type)} sent`;
};

function RecipientSearchList({ groups, value, role, onRoleChange, roleOptions, search, onSearch, onSelect, selectedRecipient, compact = false, onClose }) {
  const hasOptions = groups.some((group) => group.recipients.length > 0);

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-bold text-text-soft sm:text-sm">
          <SlidersHorizontal className="h-3.5 w-3.5 text-text-faint" /> Filter recipient role
        </span>
        {onClose ? (
          <Button type="button" variant="ghost" size="icon" aria-label="Close recipient filters" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        ) : null}
      </div>
      <label className="block text-xs font-semibold text-text-soft sm:text-sm">
        <select
          className="input-base"
          value={role}
          onChange={(event) => onRoleChange(event.target.value)}
        >
          <option value="all">All permitted roles</option>
          {roleOptions.map((item) => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
      </label>
      <div className="relative">
        <Input
          label="Recipient"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Type a name or email"
          className="pl-9"
        />
        <Search className="pointer-events-none absolute bottom-3 left-3 h-4 w-4 text-text-faint" />
      </div>
      <div className={`${compact ? "max-h-44 sm:max-h-56" : "max-h-64"} overflow-y-auto rounded-lg border border-border bg-surface shadow-sm`}>
        {hasOptions ? (
          groups.map((group) => (
            <div key={group.label} className="border-b border-border last:border-b-0">
              <p className="bg-surface-muted/50 px-3 py-2 text-xs font-bold uppercase text-text-faint">{group.label}</p>
              {group.recipients.map((recipient) => {
                const recipientValue = `${recipient.actor_type}:${recipient.actor_id}`;
                const isSelected = recipientValue === value;
                return (
                  <button
                    key={recipientValue}
                    type="button"
                    onClick={() => onSelect(recipientValue)}
                    className={`block w-full px-3 py-2 text-left ${isSelected ? "is-selected-highlight" : "hover:bg-surface-muted/60"}`}
                  >
                    <span className="flex items-center justify-between gap-3">
                      <span className="block truncate text-sm font-semibold">{recipient.label}</span>
                      {isSelected ? <span className="text-xs font-bold">Selected</span> : null}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-text-muted">{recipient.group_label || group.label}</span>
                  </button>
                );
              })}
            </div>
          ))
        ) : (
          <p className="px-3 py-4 text-sm text-text-muted">No permitted recipients match that search.</p>
        )}
      </div>
      {selectedRecipient ? <p className="text-xs font-semibold text-primary">Selected: {selectedRecipient.label}</p> : null}
    </div>
  );
}

export default function MessagesPage() {
  const [conversations, setConversations] = useState([]);
  const [conversationTotal, setConversationTotal] = useState(0);
  const [conversationPage, setConversationPage] = useState(1);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState(null);
  const [recipientGroups, setRecipientGroups] = useState([]);
  const [recipientRole, setRecipientRole] = useState("all");
  const [recipientKey, setRecipientKey] = useState("");
  const [recipientSearch, setRecipientSearch] = useState("");
  const [body, setBody] = useState("");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [composeError, setComposeError] = useState("");
  const [replyError, setReplyError] = useState("");
  const [sendingNew, setSendingNew] = useState(false);
  const [sendingReply, setSendingReply] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);

  const currentUser = authSession.getUser() || {};
  const tokenPayload = useMemo(() => decodeTokenPayload(authSession.getToken?.()), []);
  const currentActorType = currentUser.actor_type || tokenPayload.actor_type || authRoleToActorType[currentUser.role] || currentUser.role || "";
  const currentActorId = currentUser.membership_id || currentUser.actor_id || tokenPayload.sub || currentUser.id;
  const currentActorKey = `${currentActorType}:${currentActorId}`;
  const recipients = useMemo(() => flattenRecipients(recipientGroups), [recipientGroups]);
  const identityDirectory = useMemo(() => {
    const rows = {};
    recipients.forEach((recipient) => {
      rows[actorKeyFor(recipient)] = recipient;
    });
    [...conversations, selected].filter(Boolean).forEach((conversation) => {
      (conversation.participants || []).forEach((participant) => {
        const key = actorKeyFor(participant);
        if (!rows[key]) rows[key] = participant;
      });
    });
    if (!rows[currentActorKey]) {
      rows[currentActorKey] = {
        actor_type: currentActorType,
        actor_id: currentActorId,
        label: currentUserLabel(currentUser, currentActorType, currentActorId),
        group_label: roleLabel(currentActorType),
      };
    }
    return rows;
  }, [conversations, currentActorId, currentActorKey, currentActorType, currentUser, recipients, selected]);
  const roleOptions = useMemo(() => {
    const actorTypes = [...new Set(recipients.map((recipient) => recipient.actor_type).filter(Boolean))];
    return actorTypes.map((actorType) => ({ value: actorType, label: roleLabel(actorType) }));
  }, [recipients]);
  const conversationPageCount = Math.max(1, Math.ceil(conversationTotal / CONVERSATION_PAGE_SIZE));
  const selectedRecipient = useMemo(
    () => recipients.find((recipient) => `${recipient.actor_type}:${recipient.actor_id}` === recipientKey),
    [recipientKey, recipients],
  );
  const filteredRecipientGroups = useMemo(() => {
    const query = recipientSearch.trim().toLowerCase();
    return (recipientGroups || [])
      .map((group) => ({
        ...group,
        recipients: (group.recipients || []).filter(
          (recipient) =>
            (recipientRole === "all" || recipient.actor_type === recipientRole) &&
            (!query ||
              `${recipient.label} ${recipient.group_label || ""} ${recipient.actor_id}`
                .toLowerCase()
                .includes(query)),
        ),
      }))
      .filter((group) => group.recipients.length > 0);
  }, [recipientGroups, recipientRole, recipientSearch]);
  const dashboardRole = String(currentUser.role || "admin").toLowerCase();

  const handleRoleChange = (nextRole) => {
    setRecipientRole(nextRole);
    setRecipientKey("");
    setRecipientSearch("");
  };

  const selectRecipient = (nextRecipientKey) => {
    setRecipientKey(nextRecipientKey);
    setComposerOpen(false);
  };

  const load = useCallback(async () => {
      setLoading(true);
      setError("");
      try {
      const skip = (conversationPage - 1) * CONVERSATION_PAGE_SIZE;
      const [conversationResponse, recipientResponse] = await Promise.all([
        messageService.listConversations({ skip, limit: CONVERSATION_PAGE_SIZE }),
        messageService.availableRecipients(),
      ]);
      const rows = conversationResponse?.items || [];
      setConversations(rows);
      setConversationTotal(Number(conversationResponse?.total || rows.length));
      setRecipientGroups(recipientResponse?.groups || []);
      if (!selectedId && rows[0]?.id) setSelectedId(rows[0].id);
    } catch (err) {
      setError(getErrorMessage(err, "Could not load messages."));
    } finally {
      setLoading(false);
    }
  }, [conversationPage, selectedId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    let mounted = true;
    messageService.getConversation(selectedId)
      .then((response) => {
        if (mounted) setSelected(response);
      })
      .catch((err) => {
        if (mounted) setError(getErrorMessage(err, "Could not open conversation."));
      });
    return () => {
      mounted = false;
    };
  }, [selectedId]);

  const sendNew = async (event) => {
    event.preventDefault();
    setComposeError("");
    const recipient = recipients.find((item) => `${item.actor_type}:${item.actor_id}` === recipientKey);
    if (!recipient) {
      setComposeError("Choose a recipient first.");
      return;
    }
    if (!body.trim()) {
      setComposeError("Write a message before sending.");
      return;
    }
    setSendingNew(true);
    try {
      const conversation = await messageService.createConversation({
        recipient: { actor_type: recipient.actor_type, actor_id: recipient.actor_id },
        body: body.trim(),
      });
      setBody("");
      setRecipientKey("");
      setRecipientSearch("");
      setComposerOpen(false);
      setConversationPage(1);
      setSelectedId(conversation.id);
      await load();
    } catch (err) {
      setComposeError(getErrorMessage(err, "Could not send message."));
    } finally {
      setSendingNew(false);
    }
  };

  const sendReply = async (event) => {
    event.preventDefault();
    setReplyError("");
    if (!selected?.id) return;
    if (!reply.trim()) {
      setReplyError("Write a reply before sending.");
      return;
    }
    setSendingReply(true);
    try {
      await messageService.sendMessage(selected.id, { body: reply.trim() });
      setReply("");
      const refreshed = await messageService.getConversation(selected.id);
      setSelected(refreshed);
      await load();
    } catch (err) {
      setReplyError(getErrorMessage(err, "Could not send reply."));
    } finally {
      setSendingReply(false);
    }
  };

  const composingNew = composerOpen && Boolean(selectedRecipient);

  const sendActiveMessage = async (event) => {
    if (selected?.id && !composingNew) {
      await sendReply(event);
      return;
    }
    await sendNew(event);
  };

  const chatInputValue = selected?.id && !composingNew ? reply : body;
  const setChatInputValue = selected?.id && !composingNew ? setReply : setBody;
  const chatError = selected?.id && !composingNew ? replyError : composeError;
  const isSending = selected?.id && !composingNew ? sendingReply : sendingNew;
  const canSend = selected?.id && !composingNew ? Boolean(reply.trim()) : Boolean(selectedRecipient && body.trim());

  return (
    <DashboardLayout role={dashboardRole}>
    <section className="grid h-[calc(100dvh-6.5rem)] min-h-[34rem] w-full grid-rows-[auto_minmax(0,1fr)] gap-3 overflow-hidden lg:h-[calc(100dvh-8rem)] lg:grid-cols-[20rem_minmax(0,1fr)] lg:grid-rows-1 lg:gap-4 xl:grid-cols-[23rem_minmax(0,1fr)]">
      <aside className="min-h-0 overflow-hidden rounded-2xl border border-border bg-surface">
        <div className="border-b border-border px-3 py-3 sm:px-4">
          <h2 className="text-base font-bold text-text sm:text-lg">Conversations</h2>
          <p className="mt-0.5 text-xs text-text-muted sm:text-sm">Recent direct chats.</p>
        </div>
        <div className="mobile-scroll-list grid max-h-[10rem] grid-cols-1 gap-2 overflow-y-auto p-2 sm:max-h-[13rem] lg:block lg:max-h-none lg:p-0">
          {loading ? <LoadingState label="Loading conversations" /> : null}
          {!loading && conversations.map((conversation) => {
            const latestMessage = conversation.messages?.at(-1);
            const active = selectedId === conversation.id;
            return (
              <button
                key={conversation.id}
                type="button"
                onClick={() => setSelectedId(conversation.id)}
                className={`block min-h-[5.25rem] w-full rounded-xl border px-3 py-3 text-left lg:min-h-0 lg:rounded-none lg:border-x-0 lg:border-t-0 lg:px-4 ${active ? "border-primary/70 bg-primary text-text-inverse shadow-sm" : "border-border/70 hover:bg-surface-muted/50"}`}
              >
                <span className="flex items-center justify-between gap-3">
                  <span className={`truncate text-sm font-bold ${active ? "text-text-inverse" : "text-text"}`}>{latestSenderTitle(conversation, identityDirectory)}</span>
                  {conversation.unread_count ? <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${active ? "bg-white/20 text-white" : "bg-primary text-white"}`}>{conversation.unread_count}</span> : null}
                </span>
                <span className={`mt-1 block truncate text-[11px] font-semibold uppercase ${active ? "text-white/70" : "text-text-faint"}`}>{latestSenderMeta(conversation, currentActorKey, identityDirectory)}</span>
                <span className={`mt-1 block truncate text-xs ${active ? "text-white/80" : "text-text-muted"}`}>{latestMessage?.body || "No messages yet"}</span>
              </button>
            );
          })}
          {!loading && !conversations.length ? <div className="p-4"><EmptyState icon={MessageCircle} title="No conversations yet" /></div> : null}
        </div>
        <div className="mobile-list-pagination flex items-center justify-between gap-2 px-3 pb-3 text-xs text-text-muted sm:px-4">
          <span>Page {conversationPage} of {conversationPageCount}</span>
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              size="xs"
              variant="outline"
              disabled={loading || conversationPage <= 1}
              onClick={() => setConversationPage((current) => Math.max(1, current - 1))}
            >
              Previous
            </Button>
            <Button
              type="button"
              size="xs"
              variant="outline"
              disabled={loading || conversationPage >= conversationPageCount}
              onClick={() => setConversationPage((current) => Math.min(conversationPageCount, current + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      </aside>

      <main className="min-h-0 overflow-hidden rounded-2xl border border-border bg-surface">
        {error ? <div className="border-b border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div> : null}
        {!selected ? (
          <div className="flex h-full min-h-0 flex-col">
            <div className="border-b border-border px-3 py-3 sm:px-4">
              <h2 className="font-bold text-text">New chat</h2>
              <p className="mt-1 text-xs text-text-muted">Choose the exact recipient under the message box.</p>
            </div>
            <div className="min-h-0 flex-1 bg-surface-muted/20 p-4">
              <EmptyState icon={MessageCircle} title="Start a conversation" />
            </div>
            <form onSubmit={sendActiveMessage} className="border-t border-border bg-surface p-2.5 sm:p-3">
              {composerOpen ? (
                <div className="mb-3 rounded-2xl border border-border bg-surface-muted/25 p-3">
                  <RecipientSearchList
                    groups={filteredRecipientGroups}
                    value={recipientKey}
                    role={recipientRole}
                    onRoleChange={handleRoleChange}
                    roleOptions={roleOptions}
                    search={recipientSearch}
                    onSearch={setRecipientSearch}
                    onSelect={selectRecipient}
                    selectedRecipient={selectedRecipient}
                    compact
                    onClose={() => setComposerOpen(false)}
                  />
                </div>
              ) : null}
              {chatError ? <p className="mb-2 text-xs font-semibold text-error">{chatError}</p> : null}
              <div className="flex items-end gap-2">
                <Button type="button" variant="outline" size="icon" aria-label="Choose recipient" onClick={() => setComposerOpen((current) => !current)}>
                  <UserPlus className="h-4 w-4" />
                </Button>
                <textarea
                  className="input-base min-h-11 flex-1 resize-none rounded-2xl"
                  value={chatInputValue}
                  onChange={(event) => setChatInputValue(event.target.value)}
                  placeholder={selectedRecipient ? `Message ${selectedRecipient.label}` : "Choose a recipient, then write a message"}
                />
                <Button type="submit" aria-label="Send message" disabled={isSending || !canSend}>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </form>
          </div>
        ) : (
          <div className="flex h-full min-h-0 flex-col">
            <div className="border-b border-border px-3 py-3 sm:px-4">
              <h2 className="font-bold text-text">{conversationTitle(selected, currentActorKey, identityDirectory)}</h2>
              <p className="mt-1 text-xs font-semibold uppercase text-text-faint">
                {(selected.participants || [])
                  .map((participant) => identityMeta(identityDirectory[actorKeyFor(participant)] || participant))
                  .filter(Boolean)
                  .join(" / ") || selected.conversation_type || "direct"}
              </p>
            </div>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto bg-surface-muted/20 p-3 sm:p-4">
              {(selected.messages || []).map((message) => {
                const mine = `${message.sender_actor_type}:${message.sender_actor_id}` === currentActorKey;
                const sender = identityDirectory[`${message.sender_actor_type}:${message.sender_actor_id}`] || {
                  actor_type: message.sender_actor_type,
                  actor_id: message.sender_actor_id,
                };
                return (
                  <article key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[88%] rounded-2xl px-3 py-2.5 shadow-sm sm:max-w-[82%] sm:px-4 sm:py-3 ${mine ? "rounded-br-md bg-primary text-white" : "rounded-bl-md border border-border bg-surface text-text"}`}>
                      <p className={`mb-1 text-[11px] font-bold uppercase ${mine ? "text-white/75" : "text-text-faint"}`}>
                        {identityLabel(sender, currentActorKey, { useSelfLabel: false })}
                      </p>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.body}</p>
                      <time className={`mt-2 block text-[11px] ${mine ? "text-white/75" : "text-text-faint"}`}>{new Date(message.created_at).toLocaleString()}</time>
                    </div>
                  </article>
                );
              })}
            </div>
            <form onSubmit={sendActiveMessage} className="border-t border-border bg-surface p-2.5 sm:p-3">
              {composerOpen ? (
                <div className="mb-3 rounded-2xl border border-border bg-surface-muted/25 p-3">
                  <RecipientSearchList
                    groups={filteredRecipientGroups}
                    value={recipientKey}
                    role={recipientRole}
                    onRoleChange={handleRoleChange}
                    roleOptions={roleOptions}
                    search={recipientSearch}
                    onSearch={setRecipientSearch}
                    onSelect={selectRecipient}
                    selectedRecipient={selectedRecipient}
                    compact
                    onClose={() => setComposerOpen(false)}
                  />
                </div>
              ) : null}
              {chatError ? <p className="mb-2 text-xs font-semibold text-error">{chatError}</p> : null}
              <div className="flex items-end gap-2">
                <Button type="button" variant="outline" size="icon" aria-label="Start new chat" onClick={() => setComposerOpen((current) => !current)}>
                  <UserPlus className="h-4 w-4" />
                </Button>
                <textarea
                  className="input-base min-h-11 flex-1 resize-none rounded-2xl"
                  value={chatInputValue}
                  onChange={(event) => setChatInputValue(event.target.value)}
                  placeholder={composingNew ? `Message ${selectedRecipient.label}` : "Write a reply"}
                />
                <Button type="submit" aria-label="Send reply" disabled={isSending || !canSend}>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </form>
          </div>
        )}
      </main>
    </section>
    </DashboardLayout>
  );
}
