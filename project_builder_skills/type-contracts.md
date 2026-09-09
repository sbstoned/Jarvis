# Type and contract convergence

- Shared domain types, DTOs, interfaces, enums, schemas, headers, and protocols need one authoritative owner per component/language.
- Consumers import/use the owner. Do not redefine the same public contract in stores, controllers, routes, views, tests, or commands.
- When compiler errors disagree on collection shape, identifier type, enum values, nullability, field names, or serialization, inspect the canonical type/provider first.
- Cross-language copies may exist only when they are serialization-compatible and intentionally owned by separate components.
- Preserve public contracts unless real compiler/test/consumer evidence proves the contract itself is wrong.

## V42.22 stable-provider protection

- Clean accepted files under semantic type/contract/model/schema directories are stable contract providers.
- Do not add unrelated fields to a DTO merely to satisfy a UI Props interface. Wire the real state/hook/producer into the consuming component instead.
- Comments or changes that explicitly say a domain field was added only to satisfy unrelated `*Props` are architectural smell and should be removed/reconciled at the consumer layer.
- Import/export compiler errors may legitimately require provider changes; ordinary consumer prop/argument errors do not.
