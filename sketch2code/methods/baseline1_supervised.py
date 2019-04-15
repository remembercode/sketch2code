#!/usr/bin/python
# -*- coding: utf-8 -*-
import math
from typing import *
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm

from sketch2code.methods.dqn import conv2d_size_out, pool2d_size_out
from sketch2code.methods.lstm import LSTM, prepare_batch_sent_lbls, padded_aware_nllloss


class BLSuper1(nn.Module):

    def __init__(self, img_h: int, img_w: int, dsl_vocab: Dict[int, str], dsl_embedding_dim: int, dsl_hidden_dim: int):
        super().__init__()
        self.img_w = img_w
        self.img_h = img_h
        self.dsl_vocab = dsl_vocab
        self.dsl_hidden_dim = dsl_hidden_dim
        self.dsl_embedding_dim = dsl_embedding_dim

        self.__build_model()

    def __build_model(self):
        # network compute features of target image
        self.conv1 = nn.Conv2d(3, 16, kernel_size=7, stride=2)
        self.bn1 = nn.BatchNorm2d(16, momentum=0.9)
        self.pool1 = nn.MaxPool2d(kernel_size=3, stride=2)

        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=1)
        self.bn2 = nn.BatchNorm2d(32, momentum=0.9)
        self.pool2 = nn.MaxPool2d(kernel_size=3, stride=2)

        imgsize = [self.img_w, self.img_h]
        for i, s in enumerate(imgsize):
            s = conv2d_size_out(s, 7, 2)
            s = pool2d_size_out(s, 3, 2)
            s = conv2d_size_out(s, 5, 1)
            s = pool2d_size_out(s, 3, 2)
            imgsize[i] = s

        linear_input_size = imgsize[0] * imgsize[1] * 32

        self.img2hidden = nn.Linear(linear_input_size, self.dsl_hidden_dim)

        # compute features from programs
        self.lstm = LSTM(
            vocab_size=len(self.dsl_vocab),
            padding_token_idx=self.dsl_vocab['<pad>'],
            embedding_dim=self.dsl_embedding_dim,
            hidden_size=self.dsl_hidden_dim,
            n_layers=1)

        self.hidden2token = nn.Linear(self.dsl_hidden_dim, len(self.dsl_vocab))

    def forward(self, x1, x2, x2_lens):
        """
            @x1: desired images (batch: N x C x W x H)
            @x2: current programs (batch: N x T)
            @x2_lens: lengths of current programs (N)
        """
        batch_size = x2_lens.shape[0]

        x1 = self.pool1(F.relu(self.bn1(self.conv1(x1))))
        x1 = self.pool2(F.relu(self.bn2(self.conv2(x1))))

        # reshape from N x C x W x H to N x (C * W * H)
        x1 = x1.view(batch_size, -1)
        h0 = F.relu(self.img2hidden(x1)).view(1, batch_size, self.dsl_hidden_dim)
        c0 = self.lstm.init_hidden_cn(x2, batch_size)
        x2, (hn, cn) = self.lstm(x2, x2_lens, (h0, c0))

        # flatten from N x T x H to N x (T * H)
        x2 = x2.contiguous().view(-1, self.dsl_hidden_dim)

        tokens = self.hidden2token(x2)
        tokens = F.log_softmax(tokens, dim=1)
        return tokens


class BLSuper2(nn.Module):

    def __init__(self, img_h: int, img_w: int, dsl_vocab: Dict[int, str], dsl_embedding_dim: int, dsl_hidden_dim: int):
        super().__init__()
        self.img_w = img_w
        self.img_h = img_h
        self.dsl_vocab = dsl_vocab
        self.dsl_hidden_dim = dsl_hidden_dim
        self.dsl_embedding_dim = dsl_embedding_dim

        self.__build_model()

    def __build_model(self):
        # network compute features of target image
        self.conv1 = nn.Conv2d(3, 16, kernel_size=7, stride=2)
        self.bn1 = nn.BatchNorm2d(16, momentum=0.9)
        self.pool1 = nn.MaxPool2d(kernel_size=3, stride=2)

        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=1)
        self.bn2 = nn.BatchNorm2d(32, momentum=0.9)
        self.pool2 = nn.MaxPool2d(kernel_size=3, stride=2)

        imgsize = [self.img_w, self.img_h]
        for i, s in enumerate(imgsize):
            s = conv2d_size_out(s, 7, 2)
            s = pool2d_size_out(s, 3, 2)
            s = conv2d_size_out(s, 5, 1)
            s = pool2d_size_out(s, 3, 2)
            imgsize[i] = s

        linear_input_size = imgsize[0] * imgsize[1] * 32

        self.img2hidden = nn.Linear(linear_input_size, self.dsl_hidden_dim)

        # compute features from programs
        self.lstm = LSTM(
            vocab_size=len(self.dsl_vocab),
            padding_token_idx=self.dsl_vocab['<pad>'],
            embedding_dim=self.dsl_embedding_dim,
            hidden_size=self.dsl_hidden_dim,
            n_layers=1)

        self.hidden2token = nn.Linear(self.dsl_hidden_dim, len(self.dsl_vocab))

    def forward(self, x1, x2, x2_lens):
        """
            @x1: desired images (batch: N x C x W x H)
            @x2: current programs (batch: N x T)
            @x2_lens: lengths of current programs (N)
        """
        batch_size = x2_lens.shape[0]

        x1 = self.pool1(F.relu(self.conv1(x1)))
        x1 = self.pool2(F.relu(self.conv2(x1)))

        # reshape from N x C x W x H to N x (C * W * H)
        x1 = x1.view(batch_size, -1)
        h0 = F.relu(self.img2hidden(x1)).view(1, batch_size, self.dsl_hidden_dim)
        c0 = self.lstm.init_hidden_cn(x2, batch_size)
        x2, (hn, cn) = self.lstm(x2, x2_lens, (h0, c0))

        # flatten from N x T x H to N x (T * H)
        x2 = x2.contiguous().view(-1, self.dsl_hidden_dim)

        tokens = self.hidden2token(x2)
        tokens = F.log_softmax(tokens, dim=1)
        return tokens


def iter_batch(batch_size: int, imgs, X, y, shuffle: bool = False, device=None):
    index = list(range(len(X)))
    if shuffle:
        np.random.shuffle(index)

    for i in range(0, len(X), batch_size):
        batch_idx = index[i:i + batch_size]
        bimgs = torch.tensor([imgs[j] for j in batch_idx], dtype=torch.float32, device=device)
        bx, by, bxlen = prepare_batch_sent_lbls([X[j] for j in batch_idx], [y[j] for j in batch_idx], device=device)
        yield (bimgs, bx, bxlen, by)


def eval(model, imgs, X, y, device=None):
    losses = []
    accuracies = []
    n_tokens = 0

    batch_size = 500
    model.eval()
    with torch.no_grad():
        for bimgs, bx, bxlen, by in tqdm(iter_batch(batch_size, imgs, X, y, device=device), desc='eval',
                                         total=math.ceil(len(X) / batch_size)):
            by_pred = model(bimgs, bx, bxlen)
            loss, mask, btokens = padded_aware_nllloss(by_pred, by)
            losses.append(loss.item())

            n_tokens += btokens
            accuracies.append(((torch.argmax(by_pred, dim=1) == by.view(-1)).float() * mask).sum().item())

    model.train()
    return np.mean(losses), sum(accuracies) / n_tokens