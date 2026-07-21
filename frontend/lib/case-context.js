import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import { fetcher } from './api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const CaseContext = createContext(null);

export function CaseProvider({ children }) {
  const { data, mutate } = useSWR(apiUrl('/api/household/members'), fetcher);
  const members = data?.members || [];
  const [selectedTaxpayerId, setSelectedTaxpayerId] = useState(null);
  const [selectedCaseId, setSelectedCaseId] = useState(null);

  useEffect(() => {
    const storedTaxpayer = Number(globalThis?.localStorage?.getItem('selectedTaxpayerId') || 0);
    const storedCase = Number(globalThis?.localStorage?.getItem('selectedCaseId') || 0);
    if (storedTaxpayer) setSelectedTaxpayerId(storedTaxpayer);
    if (storedCase) setSelectedCaseId(storedCase);
  }, []);

  useEffect(() => {
    if (!members.length) return;
    const selectedMember = members.find((m) => m.id === selectedTaxpayerId) || members[0];
    const selectedCase = selectedMember?.cases?.find((c) => c.id === selectedCaseId) || selectedMember?.cases?.[0] || null;
    if (selectedMember && selectedMember.id !== selectedTaxpayerId) {
      setSelectedTaxpayerId(selectedMember.id);
      globalThis?.localStorage?.setItem('selectedTaxpayerId', String(selectedMember.id));
    }
    if (selectedCase && selectedCase.id !== selectedCaseId) {
      setSelectedCaseId(selectedCase.id);
      globalThis?.localStorage?.setItem('selectedCaseId', String(selectedCase.id));
    }
  }, [members, selectedTaxpayerId, selectedCaseId]);

  const setSelection = (taxpayerId, caseId) => {
    setSelectedTaxpayerId(taxpayerId);
    setSelectedCaseId(caseId);
    globalThis?.localStorage?.setItem('selectedTaxpayerId', String(taxpayerId));
    globalThis?.localStorage?.setItem('selectedCaseId', String(caseId));
  };

  const selectedMember = members.find((m) => m.id === selectedTaxpayerId) || null;
  const selectedCase = selectedMember?.cases?.find((c) => c.id === selectedCaseId) || null;

  const value = useMemo(
    () => ({
      members,
      selectedTaxpayerId,
      selectedCaseId,
      selectedMember,
      selectedCase,
      setSelection,
      refreshMembers: mutate,
    }),
    [members, selectedTaxpayerId, selectedCaseId, selectedMember, selectedCase, mutate]
  );

  return <CaseContext.Provider value={value}>{children}</CaseContext.Provider>;
}

export function useCaseContext() {
  const context = useContext(CaseContext);
  if (!context) {
    throw new Error('useCaseContext must be used inside CaseProvider');
  }
  return context;
}
