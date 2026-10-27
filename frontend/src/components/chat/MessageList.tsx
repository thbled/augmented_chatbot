import type { ChatMessage } from '../../types/chat';
import { AssistantMessage } from './AssistantMessage';
import { UserMessage } from './UserMessage';

interface MessageListProps {
  messages: ChatMessage[];
  onRetry: () => void;
}

export function MessageList({ messages, onRetry }: MessageListProps) {
  return (
    <div className="space-y-6">
      {messages.map((message, index) =>
        message.role === 'user' ? (
          <UserMessage key={message.id} content={message.content} />
        ) : (
          <AssistantMessage
            key={message.id}
            message={message}
            isLast={index === messages.length - 1}
            onRetry={onRetry}
          />
        ),
      )}
    </div>
  );
}
