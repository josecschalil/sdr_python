%% ===================== RECEIVER =====================
clear; clc;

fs = 48000;

% Pluto SDR RX
rx = sdrrx('Pluto');
rx.CenterFrequency = 433e6;
rx.BasebandSampleRate = fs;
rx.SamplesPerFrame = 48000;
rx.OutputDataType = 'double';

disp('Receiving...');
rxSignal = rx();

release(rx);

% FM Demodulation (simple)
demod = angle(rxSignal(2:end).*conj(rxSignal(1:end-1)));

% Normalize
demod = demod / max(abs(demod));

% Bandpass filters for AFSK
bp1 = designfilt('bandpassiir','FilterOrder',4,...
    'HalfPowerFrequency1',1000,'HalfPowerFrequency2',1400,...
    'SampleRate',fs);

bp2 = designfilt('bandpassiir','FilterOrder',4,...
    'HalfPowerFrequency1',2000,'HalfPowerFrequency2',2400,...
    'SampleRate',fs);

sig1 = filter(bp1, demod);
sig2 = filter(bp2, demod);

% Bit recovery
bitrate = 1200;
samplesPerBit = fs/bitrate;

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

% Convert bits → characters
bits = bits(1:floor(length(bits)/8)*8);
bytes = reshape(bits,8,[]).';
chars = char(bin2dec(num2str(bytes)));

disp('Received Message:');
disp(chars);