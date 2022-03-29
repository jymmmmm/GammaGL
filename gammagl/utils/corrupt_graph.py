import tensorlayerx as tlx
import tensorflow as tf
import scipy.sparse as sp
from gammagl.data import Graph
import numpy as np


def calc(edge, num_node):
    weight = np.ones(edge.shape[1])
    sparse_adj = sp.coo_matrix((weight, (edge[0], edge[1])), shape=(num_node, num_node))
    A = (sparse_adj + sp.eye(num_node)).tocoo()
    col, row, weight = A.col, A.row, A.data
    deg = np.array(A.sum(1))
    deg_inv_sqrt = np.power(deg, -0.5).flatten()

    return col, row, np.array(deg_inv_sqrt[row] * weight * deg_inv_sqrt[col], dtype=np.float32)


def dfde_norm_g(edge_index, feat, feat_drop_rate, drop_edge_rate):
    num_node = feat.shape[0]
    edge_mask = drop_edge(edge_index, drop_edge_rate)
    new_edge = tlx.transpose(edge_index)[edge_mask]
    # tlx can't assignment, so still use tf
    feat = drop_feat(feat, feat_drop_rate)
    row, col, weight = calc(tlx.transpose(new_edge), num_node)
    new_g = Graph(edge_index=tlx.convert_to_tensor([row, col], dtype=tlx.int64), x=feat, num_nodes=num_node)
    new_g.edge_weight = weight

    return new_g


def drop_edge(edge_index, drop_edge_rate):
    if drop_edge_rate < 0. or drop_edge_rate > 1.:
        raise ValueError(f'Dropout probability has to be between 0 and 1 '
                         f'(got {drop_edge_rate}')
    if drop_edge_rate == 0.:
        return tlx.convert_to_tensor(np.ones(edge_index.shape[1], dtype=np.bool8))
    mask = tlx.ops.random_uniform(shape=[edge_index.shape[1]],
                                  minval=0, maxval=1, dtype=tlx.float32) >= drop_edge_rate
    return mask


def drop_feat(feat, drop_feat_rate):
    if drop_feat_rate < 0. or drop_feat_rate > 1.:
        raise ValueError(f'Dropout probability has to be between 0 and 1 '
                         f'(got {drop_feat_rate}')
    if drop_feat_rate == 0.:
        drop_mask = tlx.convert_to_tensor(np.ones(feat.shape[1], dtype=np.bool8))
    else:
        drop_mask = tlx.ops.random_uniform(shape=[feat.shape[1]],
                                       minval=0, maxval=1, dtype=tlx.float32) < drop_feat_rate
    # update tlx don't have
    drop_mask = tlx.range(0, drop_mask.shape)[drop_mask]
    zero = tlx.zeros((drop_mask.shape[0], feat.shape[0]), dtype=tlx.float32)
    feat = tf.tensor_scatter_nd_update(tlx.transpose(feat), tlx.expand_dims(drop_mask, -1), zero)
    feat = tlx.transpose(feat)

    return feat


# a = tlx.convert_to_tensor(np.arange(0, 10, dtype=np.float32).reshape(2, -1))
# # b = tlx.convert_to_tensor(np.ones(shape=[2], dtype=np.bool8))
# b = drop_feat(a, 0.5)
# print(b)