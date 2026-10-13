import {useEffect, useRef, useState} from 'react';
import type {Snapshot} from '../types';
import {FrameDecoder, type DecodedFrame} from '../utils/snapshotState';

export function useDecodedSnapshot(snapshot: Snapshot | null) {
  const [frame, setFrame] = useState<DecodedFrame | null>(null);
  const [error, setError] = useState('');
  const decoder = useRef<FrameDecoder | null>(null);
  if (!decoder.current) decoder.current = new FrameDecoder(frame => {setFrame(frame); setError('');}, () => setError('视频帧解码失败，请暂停后重试'));
  useEffect(() => {if (snapshot) decoder.current!.update(snapshot);}, [snapshot]);
  useEffect(() => () => decoder.current?.cancel(), []);
  return {frame: frame?.snapshot.video_token === snapshot?.video_token && frame?.snapshot.session_id === snapshot?.session_id ? frame : null, error};
}
