import { ChevronDown, PlusCircle, Ban } from 'lucide-react';
import { useState } from 'react';

import type { ChatModelConfig } from '@/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuPortal,
	DropdownMenuSeparator,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useAvailableModels } from '@/hooks/useAvailableModels';
import { useTranslation } from '@/i18n/useI18n.ts';
import { cn } from '@/lib/utils';
import { credentialLabel } from '@/utils/common';

interface Props extends Omit<React.ComponentPropsWithoutRef<typeof Button>, 'onChange' | 'value'> {
	value?: ChatModelConfig | null;
	/**
	 * Called when the user selects a model, or — when `allowClear` is true —
	 * clears the selection (in which case `null` is emitted).
	 */
	onChange?: (value: ChatModelConfig | null) => void;
	onAddCredential?: () => void;
	/** Override the trigger label shown when no model is selected. */
	placeholder?: string;
	/**
	 * When true, append a "clear selection" item to the dropdown that emits
	 * `null` via `onChange`. Used by the fallback selector.
	 */
	allowClear?: boolean;
	/** Override the label of the "clear selection" item. */
	clearLabel?: string;
}

export function LlmSelect({
	value,
	onChange,
	onAddCredential,
	placeholder,
	allowClear = false,
	clearLabel,
	className,
	...props
}: Props) {
	const { groups, loading } = useAvailableModels();
	const { t } = useTranslation();
	const [failoverOpen, setFailoverOpen] = useState(false);
	const [fallbackNames, setFallbackNames] = useState('');
	const [fromCatalog, setFromCatalog] = useState(false);
	const [timeout, setTimeoutSeconds] = useState('60');
	// Credentials whose model list failed to load come back with an empty
	// `models` array; drop them so they don't render empty submenus
	const groupEntries = Object.entries(groups)
		.map(([type, items]) => [type, items.filter((i) => i.models.length > 0)] as const)
		.filter(([, usable]) => usable.length > 0);
	const hasOptions = groupEntries.length > 0;

	const handleSelect = (type: string, credentialId: string, model: string) => {
		onChange?.({
			...(value?.credential_id === credentialId ? value : {}),
			type, credential_id: credentialId, model, parameters: {},
		});
	};

	const displayLabel = value?.model
		? value.model
		: loading
			? t('llm-select.loading')
			: (placeholder ?? t('llm-select.placeholder'));

	return (
		<>
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					variant="outline"
					size="sm"
					className={cn('justify-between gap-1 font-normal', className)}
					{...props}
				>
					<span className="truncate">{displayLabel}</span>
					<ChevronDown className="size-3.5 text-muted-foreground" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" className="min-w-48 max-h-72 overflow-y-auto">
				{!loading && !hasOptions ? (
					<div className="px-2 py-3 text-center text-sm text-muted-foreground">
						<p className="font-medium">{t('llm-select.empty.title')}</p>
						<p className="text-xs mt-1">{t('llm-select.empty.description')}</p>
					</div>
				) : (
					groupEntries.map(([type, usable], idx) => {
						const isSingle = usable.length === 1;
						return (
							<DropdownMenuGroup key={type}>
								{idx > 0 && <DropdownMenuSeparator />}
								<DropdownMenuLabel>
									{type.replace(/_credential$/, '')}
								</DropdownMenuLabel>
								{isSingle
									? usable[0].models.map((m) => (
											<DropdownMenuItem
												key={m.name}
												onSelect={() =>
													handleSelect(
														type,
														usable[0].credential.id,
														m.name,
													)
												}
											>
												{m.name}
											</DropdownMenuItem>
										))
									: usable.map(({ credential, models }) => (
											<DropdownMenuSub key={credential.id}>
												<DropdownMenuSubTrigger>
													{credentialLabel(credential)}
												</DropdownMenuSubTrigger>
												<DropdownMenuPortal>
													<DropdownMenuSubContent className="max-h-60 overflow-y-auto">
														{models.map((m) => (
															<DropdownMenuItem
																key={m.name}
																onSelect={() =>
																	handleSelect(
																		type,
																		credential.id,
																		m.name,
																	)
																}
															>
																{m.label}
															</DropdownMenuItem>
														))}
													</DropdownMenuSubContent>
												</DropdownMenuPortal>
											</DropdownMenuSub>
										))}
							</DropdownMenuGroup>
						);
					})
				)}
				<DropdownMenuSeparator />
				{!allowClear && value && (
					<DropdownMenuItem onSelect={() => {
						setFallbackNames((value.fallback_models ?? []).join('\n'));
						setFromCatalog(value.fallback_from_catalog ?? false);
						setTimeoutSeconds(String(value.request_timeout ?? 60));
						setFailoverOpen(true);
					}}>
						{t('llm-select.failover')}
					</DropdownMenuItem>
				)}
				{allowClear && (
					<DropdownMenuItem onSelect={() => onChange?.(null)} disabled={!value}>
						<Ban className="size-4" />
						<span>{clearLabel ?? t('llm-select.clear')}</span>
					</DropdownMenuItem>
				)}
				<DropdownMenuItem onSelect={onAddCredential}>
					<PlusCircle className="size-4" />
					<span>{t('llm-select.addCredential')}</span>
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
		<Dialog open={failoverOpen} onOpenChange={setFailoverOpen}>
			<DialogContent>
				<DialogTitle>{t('llm-select.failover')}</DialogTitle>
				<DialogDescription>{t('llm-select.failoverDescription')}</DialogDescription>
				<label className="flex items-center gap-2">
					<input type="checkbox" checked={fromCatalog} onChange={(e) => setFromCatalog(e.target.checked)} />
					{t('llm-select.fromCatalog')}
				</label>
				<label className="grid gap-2">
					{t('llm-select.fallbackNames')}
					<Textarea value={fallbackNames} onChange={(e) => setFallbackNames(e.target.value)} />
				</label>
				<label className="grid gap-2">
					{t('llm-select.timeout')}
					<Input type="number" min="1" step="1" value={timeout}
						onChange={(e) => setTimeoutSeconds(e.target.value)} />
				</label>
				<Button disabled={!Number.isFinite(Number(timeout)) || Number(timeout) < 1} onClick={() => {
					if (!value) return;
					onChange?.({
						...value,
						fallback_from_catalog: fromCatalog,
						fallback_models: [...new Set(fallbackNames.split(/[\n,，]/).map((name) => name.trim()).filter((name) => name && name !== value.model))],
						request_timeout: Number(timeout),
					});
					setFailoverOpen(false);
				}}>{t('llm-select.saveFailover')}</Button>
			</DialogContent>
		</Dialog>
		</>
	);
}
