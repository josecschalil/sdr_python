%% ===================== RECEIVER =====================
clear; clc;

fs = 96000;   % MUST match TX

% Pluto SDR RX
rx = sdrrx('Pluto');
rx.CenterFrequency = 433e6;
rx.BasebandSampleRate = fs;
rx.SamplesPerFrame = 96000;
rx.OutputDataType = 'double';

disp('Receiving...');
rxSignal = rx();

release(rx);

%% FM DEMODULATION
demod = angle(rxSignal(2:end).*conj(rxSignal(1:end-1)));
demod = demod / max(abs(demod));

%% AFSK FILTERS
bp1 = designfilt('bandpassiir','FilterOrder',4,...
    'HalfPowerFrequency1',1000,'HalfPowerFrequency2',1400,...
    'SampleRate',fs);

bp2 = designfilt('bandpassiir','FilterOrder',4,...
    'HalfPowerFrequency1',2000,'HalfPowerFrequency2',2400,...
    'SampleRate',fs);

sig1 = filter(bp1, demod);   % 1200 Hz (bit 1)
sig2 = filter(bp2, demod);   % 2200 Hz (bit 0)

%% BIT RECOVERY
bitrate = 1200;
samplesPerBit = fs/bitrate;   % = 80

numBits = floor(length(sig1)/samplesPerBit);
bits = zeros(1,numBits);

for i = 1:numBits
    idx = (i-1)*samplesPerBit + (1:samplesPerBit);
    
    e1 = sum(sig1(idx).^2);
    e2 = sum(sig2(idx).^2);
    
    if e1 > e2
        bits(i) = 1;
    else
        bits(i) = 0;
    end
end

%% BITS → TEXT
bits = bits(1:floor(length(bits)/8)*8);
bytes = reshape(bits,8,[]).';
chars = char(bin2dec(num2str(bytes)));

disp('Received Message:');
disp(chars);