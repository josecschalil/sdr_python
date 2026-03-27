%% ===================== TRANSMITTER =====================
clear; clc;

% Message
msg = 'HELLO JOSE';

% Convert to bits
bits = reshape(dec2bin(msg,8).'-'0',1,[]);

% Parameters
fs = 96000;              % >= 65104 (Pluto requirement)
bitrate = 1200;
samplesPerBit = fs/bitrate;   % = 80

f_mark = 1200;           % bit 1
f_space = 2200;          % bit 0

t = (0:samplesPerBit-1)/fs;

% Generate AFSK signal
afsk = [];
for b = bits
    if b == 1
        tone = sin(2*pi*f_mark*t);
    else
        tone = sin(2*pi*f_space*t);
    end
    afsk = [afsk tone];
end

% Normalize
afsk = afsk / max(abs(afsk));

% Repeat signal (improves reception)
afsk = repmat(afsk,1,5);

% ✅ Convert to COMPLEX (FIXED)
txSignal = complex(afsk, zeros(size(afsk)));

% Pluto SDR TX
tx = sdrtx('Pluto');
tx.CenterFrequency = 433e6;
tx.BasebandSampleRate = fs;
tx.Gain = -10;

disp('Transmitting...');
transmitRepeat(tx, txSignal.');

pause(10);

release(tx);
disp('Transmission stopped.');