%% ===================== TRANSMITTER =====================
clear; clc;

% Message
msg = 'HELLO JOSE';

% Convert to bits
bits = reshape(dec2bin(msg,8).'-'0',1,[]);

% Parameters
fs = 48000;              % Audio sample rate
bitrate = 1200;          % Bits per second
samplesPerBit = fs/bitrate;

f_mark = 1200;           % '1'
f_space = 2200;          % '0'

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

% Repeat signal for stability
afsk = repmat(afsk,1,5);

% Pluto SDR TX
tx = sdrtx('Pluto');
tx.CenterFrequency = 433e6;   % Adjust if needed
tx.BasebandSampleRate = fs;
tx.Gain = -10;

disp('Transmitting...');
transmitRepeat(tx, afsk.');

pause(10);   % transmit duration

release(tx);
disp('Transmission stopped.');